const { g } = require('./helper')

function service(req, res) {
  g(req)
}

module.exports = { service }
