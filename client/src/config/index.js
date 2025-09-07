/*
Environment configuration file
Development environment
Testing environment
Production environment
*/
// Current environment
const env = 'local'

const EnvConfig = {
    local: {
        baseApi: 'http://localhost:5001',
    },
    prod: {
        baseApi: 'http://localhost:5001',
    },
}

export default {
    env,
    // Mock master switch
    ...EnvConfig[env]
}