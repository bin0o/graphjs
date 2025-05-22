var nconf = require('nconf');

nconf.argv()
    .env()
    .file({ file: 'config.json' })
    .defaults({
        port: 1337,
        bindIp: '0.0.0.0'
    });

module.exports = {
    port: nconf.get('port'),
    bindIp: nconf.get('bindIp')
};
