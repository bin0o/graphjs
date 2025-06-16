function handle(req, res) {
    eval(req)
}

function createMiddleware() {
  
  return (req, res) => {
    handle(req, res)
  }
  
}

module.exports = { createMiddleware, handle }
