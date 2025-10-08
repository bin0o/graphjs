const helper = require('./helper')



function service(req, res) {
  const middleware = helper.createMiddleware(req)
  middleware()
}

module.exports = { service }
