function handle(req, res) {
    eval(req)
}

function createMiddleware(rew) {  

  return (req, res) => {
    handle(req, res, rew)
  }
  
}

module.exports = { createMiddleware, handle }
