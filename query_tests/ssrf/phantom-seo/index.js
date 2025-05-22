var phantom = require('phantom'),
  sitePage = null,
  phInstance = null,
  requestArray = [];

var prerenderPage = function(req, res, next) {
  var pageStatus = 500;
  if(req.query._escaped_fragment_) {
    var relUrl= req.query._escaped_fragment_;
    phantom.create()
      .then(function(instance) {
        phInstance = instance;
        return instance.createPage();
      })
      .then(function(page) {
        sitePage = page;
        var url = req.protocol+'://'+req.headers.host+relUrl;
        console.log('url to open', url);
        sitePage.on('onResourceRequested', function(requestData, networkRequest) {
          //console.log('requestData', requestData);
          //console.log('networkRequest', networkRequest);
          requestArray.push(requestData.id);
        });
        sitePage.on('onResourceReceived', function(response) {
          //console.log('response', response);
          var index = requestArray.indexOf(response.id);
          requestArray.splice(index, 1);
        });
        sitePage.on('onConsoleMessage', function(msg) {
          console.log('onConsoleMessage', msg);
        });
        sitePage.on('onError', function(err) {
          console.log('onError', err);
        });
        return page.open(url);

        //phantom.WebPage.open(url)
      })
      .then(function(status) {
        pageStatus = status;
        console.log('status', status);
        var interval = setInterval(function() {
          if(requestArray.length === 0) {
            clearInterval(interval);
            console.log('clearing interval');
            return sitePage.property('content')
            .then(function(content) {
              console.log('content', content);
              res.status(200).end(content);
            });
          }
        }, 500);
      })
      .catch(function(err) {
        console.log('error', err);
        res.status(500).end();
      });
  }
  else {
    next();
  }
};

module.exports = prerenderPage;
