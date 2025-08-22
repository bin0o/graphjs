function handle(req, res) {
    eval(req)
}

function createMiddleware() {  

  return (req, res) => {
    handle(req)
  }
  
}

module.exports = { createMiddleware, handle }
