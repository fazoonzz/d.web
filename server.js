const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

const {ApolloServer, gql } = require('apollo-server-express');
const Usuario = require('./models/usuario');

mongoose.connect('mongodb://localhost:27017/usuarios');
const typeDefs = gql`
    type Usuario {
        id: ID!
        nombre: String!
        password: String!
    }
    input UsuarioInput {
         nombre: String!
        password: String!
    }  
    type Alert {
        message: String!
    }
    type Query {
        getUsuarios: [Usuario]
        getUsuariosByID(id: ID!): Usuario
    }
    type Mutation {
        addUsuario(input: UsuarioInput): Usuario
        updateUsuario(id: ID!, input: UsuarioInput): Usuario
        deleteUsuario(id: ID!): Alert        
    }
`;
const resolvers = {
    Query: {
        async getUsuarios(obj) {
            const usuarios = await Usuario.find();
            return usuarios;
        },
        async getUsuariosByID(obj, { id }) {
            const usuarioBus = await Usuario.findById(id);
            if (usuarioBus == null) {
                throw new Error('Usuario no encontrado');
            } else { 
                return usuarioBus;
            }
        }
    },
    Mutation: {
        async addUsuario(obj, { input }) {
            const usuario = new Usuario(input);
            await usuario.save();
            return usuario;
        },
        async updateUsuario(obj, { id, input }) {
            const usuarioBus = await Usuario.findByIdAndUpdate(id, input);
            return usuarioBus;
        },
        async deleteUsuario(obj, {id}) {
            await Usuario.deleteOne({ _id: id });
            return {
                 message: 'Usuario eliminado' 
                }
        }
    }
};

let apolloServer = null;
const corsOptions = {
    origin: 'http://localhost:8090/',
    credentials: false
};

async function startServer() {
    apolloServer = new ApolloServer({ typeDefs, resolvers, corsOptions });
    await apolloServer.start();
    apolloServer.applyMiddleware({ app, cors: false });
}

startServer();

const app = express();
app.use(cors(corsOptions)); 
app.listen(8090, function(){
    console.log('Graphql server corriendo en http://localhost:8090/graphql');
});