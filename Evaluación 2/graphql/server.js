'use strict';
const express = require('express');
const crypto = require('crypto');
const { buildSchema, parse, validate, execute, specifiedRules, GraphQLError, Kind } = require('graphql');

const PORT = process.env.PORT || 8090;
const URLS = {
  orders: process.env.ORDERS_URL || 'http://localhost:9003',
  inventory: process.env.INVENTORY_URL || 'http://localhost:9002',
  clients: process.env.CLIENTS_URL || 'http://localhost:9001',
};
const MAX_DEPTH = 5, MAX_FIELDS = 60, MAX_QUERY = 4000, MAX_LIMIT = 20, TIMEOUT_MS = 3000;

// ---------------------------------------------------------------- secretos (Vault o SECRET_*)
let secretsCache = { t: 0, v: {} };
async function getSecrets() {
  if (Date.now() - secretsCache.t < 300000 && Object.keys(secretsCache.v).length) return secretsCache.v;
  const token = process.env.VAULT_TOKEN;
  try {
    if (!token) {
      const v = {};
      for (const [k, val] of Object.entries(process.env)) if (k.startsWith('SECRET_')) v[k.slice(7).toLowerCase()] = val;
      secretsCache = { t: Date.now(), v };
    } else {
      const r = await fetch(`${process.env.VAULT_ADDR || 'http://vault:8200'}/v1/secret/data/graphql`,
        { headers: { 'X-Vault-Token': token }, signal: AbortSignal.timeout(5000) });
      if (!r.ok) throw new Error('vault');
      secretsCache = { t: Date.now(), v: (await r.json()).data.data };
    }
  } catch (e) {
    if (!Object.keys(secretsCache.v).length) throw e; 
    console.warn('Vault no responde: se usa la copia en memoria');
  }
  return secretsCache.v;
}

function safeEqual(a, b) {
  const x = Buffer.from(String(a || '')), y = Buffer.from(String(b || ''));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

async function callService(ctx, service, path) {
  const secrets = await getSecrets();
  const r = await fetch(`${URLS[service]}${path}`, {
    headers: {
      'X-Service-Name': 'graphql', 'X-Service-Key': secrets[`to_${service}`] || '',
      'X-Correlation-Id': ctx.cid,
      'X-User-Id': ctx.user.id, 'X-User-Email': ctx.user.email, 'X-User-Roles': ctx.user.roles.join(','),
    },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`${service} respondió ${r.status}`);
  return r.json();
}

const schema = buildSchema(`
  type Producto { id: ID!  nombre: String!  descripcion: String!  categoria: String!
                  precio: Int!  personalizable: Boolean!  disponible: Boolean!  imagen: String }
  type ItemPedido { producto: Producto  nombre: String!  cantidad: Int!  precioUnitario: Int!
                    subtotal: Int!  mensaje: String }
  type EventoPedido { estado: String!  ts: Int! }
  type Cliente { id: ID!  nombre: String!  email: String!  telefono: String }
  type Pedido {
    id: ID!  estado: String!  total: Int!  fechaEntrega: String!  direccionEntrega: String!
    notas: String  creado: Int!
    items: [ItemPedido!]!
    historial: [EventoPedido!]!
    "Solo administradores"
    cliente: Cliente
  }
  type Query {
    resumenPedido(id: ID!): Pedido
    misPedidos(limit: Int = 10, offset: Int = 0): [Pedido!]!
  }
`);

function toPedido(o, ctx) {
  return {
    id: o.id, estado: o.estado, total: o.total, fechaEntrega: o.fecha_entrega,
    direccionEntrega: o.direccion_entrega, notas: o.notas, creado: o.creado,
    historial: o.historial || [],
    items: (o.items || []).map(i => ({
      nombre: i.nombre, cantidad: i.cantidad, precioUnitario: i.precio_unitario,
      subtotal: i.cantidad * i.precio_unitario, mensaje: i.mensaje,
      producto: () => ctx.productos.get(i.product_id) || null,   
    })),
    cliente: async (_args, c) => {                              
      if (!c.user.roles.includes('admin')) throw new GraphQLError('No autorizado para consultar el campo cliente');
      if (!o.cliente_id) return null;
      try {
        const p = await callService(c, 'clients', `/clients/${encodeURIComponent(o.cliente_id)}`);
        return p && { id: p.id, nombre: p.nombre, email: p.email, telefono: p.telefono };
      } catch { c.warnings.push('Datos de cliente no disponibles'); return null; }
    },
  };
}

async function precargarProductos(ctx, pedidos) {
  const ids = [...new Set(pedidos.flatMap(p => (p.items || []).map(i => i.product_id)))].slice(0, 50);
  ctx.productos = new Map();
  if (!ids.length) return;
  try {
    const lista = await callService(ctx, 'inventory', `/products?ids=${ids.join(',')}&limit=50`);
    for (const p of lista || []) ctx.productos.set(p.id, p);
  } catch { ctx.warnings.push('Catálogo no disponible: se omiten datos de producto'); }
}

const root = {
  async resumenPedido({ id }, ctx) {
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) return null;
    let o;
    try { o = await callService(ctx, 'orders', `/orders/${id}`); }
    catch { throw new GraphQLError('Servicio de pedidos no disponible'); }
    if (!o) return null;                  
    await precargarProductos(ctx, [o]);
    return toPedido(o, ctx);
  },
  async misPedidos({ limit, offset }, ctx) {
    const l = Math.max(1, Math.min(limit, MAX_LIMIT)), off = Math.max(0, offset);
    let lista;
    try { lista = await callService(ctx, 'orders', `/orders?limit=${l}&offset=${off}`); }
    catch { throw new GraphQLError('Servicio de pedidos no disponible'); }
    lista = lista || [];
    await precargarProductos(ctx, lista);
    return lista.map(o => toPedido(o, ctx));
  },
};

function depthOf(selSet, frags, d = 1) {
  if (!selSet) return d - 1;
  let max = d;
  for (const s of selSet.selections) {
    if (s.kind === Kind.FIELD) max = Math.max(max, s.selectionSet ? depthOf(s.selectionSet, frags, d + 1) : d);
    else if (s.kind === Kind.INLINE_FRAGMENT) max = Math.max(max, depthOf(s.selectionSet, frags, d));
    else if (s.kind === Kind.FRAGMENT_SPREAD) max = Math.max(max, depthOf(frags[s.name.value]?.selectionSet, frags, d));
  }
  return max;
}
function countFields(selSet, frags) {
  if (!selSet) return 0;
  let n = 0;
  for (const s of selSet.selections) {
    if (s.kind === Kind.FIELD) n += 1 + countFields(s.selectionSet, frags);
    else if (s.kind === Kind.INLINE_FRAGMENT) n += countFields(s.selectionSet, frags);
    else if (s.kind === Kind.FRAGMENT_SPREAD) n += countFields(frags[s.name.value]?.selectionSet, frags);
  }
  return n;
}
function limitsError(doc) {
  const frags = {};
  for (const d of doc.definitions) if (d.kind === Kind.FRAGMENT_DEFINITION) frags[d.name.value] = d;
  for (const d of doc.definitions) {
    if (d.kind !== Kind.OPERATION_DEFINITION) continue;
    if (d.operation !== 'query') return 'Solo se permiten consultas';
    if (depthOf(d.selectionSet, frags) > MAX_DEPTH) return `Profundidad máxima ${MAX_DEPTH}`;
    if (countFields(d.selectionSet, frags) > MAX_FIELDS) return `Máximo ${MAX_FIELDS} campos por consulta`;
  }
  return null;
}

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '16kb' }));

app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'graphql' }));

app.post('/graphql', async (req, res) => {
  const cid = req.get('x-correlation-id') || crypto.randomBytes(8).toString('hex');
  res.set('X-Correlation-Id', cid);
  try {
    const secrets = await getSecrets();
    if (req.get('x-service-name') !== 'gateway' || !safeEqual(req.get('x-service-key'), secrets.from_gateway)) {
      return res.status(403).json({ detail: 'Solicitud no autorizada' });
    }
    const uid = req.get('x-user-id');
    if (!uid) return res.status(401).json({ detail: 'Identidad no proporcionada' });
    const { query, variables, operationName } = req.body || {};
    if (typeof query !== 'string' || query.length > MAX_QUERY) {
      return res.status(400).json({ errors: [{ message: 'Consulta inválida o demasiado larga' }] });
    }
    let document;
    try { document = parse(query); } catch (e) { return res.status(400).json({ errors: [{ message: e.message }] }); }
    const vErrors = validate(schema, document, specifiedRules);
    if (vErrors.length) return res.status(400).json({ errors: vErrors.map(e => ({ message: e.message })) });
    const lim = limitsError(document);
    if (lim) return res.status(400).json({ errors: [{ message: lim }] });

    const ctx = {
      cid, warnings: [], productos: new Map(),
      user: { id: uid, email: req.get('x-user-email') || '', roles: (req.get('x-user-roles') || '').split(',').filter(Boolean) },
    };
    const result = await execute({ schema, document, rootValue: root, contextValue: ctx,
      variableValues: variables, operationName });
    const errors = (result.errors || []).map(e => ({ message: e.originalError && !(e.originalError instanceof GraphQLError) ? 'Error interno' : e.message, path: e.path }));
    for (const w of ctx.warnings) errors.push({ message: w });   
    res.json({ data: result.data, ...(errors.length ? { errors } : {}) });
  } catch (e) {
    console.error(`graphql cid=${cid} error`, e.message);
    res.status(500).json({ detail: 'Error interno del servicio' });
  }
});

if (require.main === module) {
  app.listen(PORT, () => console.log(`GraphQL Gateway privado escuchando en :${PORT}`));
}
module.exports = { app, limitsError, schema };
