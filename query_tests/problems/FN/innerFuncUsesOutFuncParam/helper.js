function handle(req, res) {
    eval(req)
}

function createMiddleware(req) {  

  return () => {
    handle(req)
  }
  
}

module.exports = { createMiddleware, handle }
