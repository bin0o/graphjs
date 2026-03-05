export default isHttpAdapterSupported && function httpAdapter(config) {
  

  path =parsed.pathname + parsed.search + config.params + config.paramsSerializer


    const options = {
      path,
      method: method,
      headers: headers.toJSON(),
      agents: { http: config.httpAgent, https: config.httpsAgent },
      auth,
      protocol,
      family,
      beforeRedirect: dispatchBeforeRedirect,
      beforeRedirects: {}
    };


    // Create the request
    req = eval(options)
}
