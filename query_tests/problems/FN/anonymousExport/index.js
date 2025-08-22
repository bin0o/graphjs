const helper = require('./helper')

function service(req, res) {
  helper(req)
}

module.exports = { service }
