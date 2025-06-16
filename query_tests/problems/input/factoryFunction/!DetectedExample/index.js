const helper = require('./helper')

const middleware = helper.createMiddleware()

function service(req, res) {
  middleware(req, res)
}

module.exports = { service }
