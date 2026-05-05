var doProxy = require('./proxy.js').doProxy;
var ProxyRequest = require('./filter.js').ProxyRequest
var api_proxy = require('./api_proxy.js');
function onProxy(request,response){
	var headers = initProxyHeaders(request);
	var host = headers.host;
	var hostname = host.replace(/\:\d+/,'') ;
	var port = host.replace(/[^\:]+[\:]?/,'')||80;
	var options = {
		port:port,host:hostname,
		method:request.method, 
		path:request.url.replace(/^http\:\/\/[^\/]+/,''), 
		headers:headers
	}
	var pr = new ProxyRequest(request);
	//console.log(options)
	doProxy(request,response,options,pr.requestFilter,pr.responseFilter);
}
function onRequest(request,response){
	var url = request.url.replace(/[#?&].*$/,'');
	if(url == '/api/proxy-list'){
		ProxyRequest.proxyList(request,response);
	}else if(url == '/api/proxy-item'){
		ProxyRequest.proxyItem(request,response);
	}else{
		api_proxy.writeStatic(request,response,function(){
			response.writeHead(200, {'Content-Type': 'text/plain'});
			response.end('ok,not found');
		})
	}
}
function initProxyHeaders(request){
	var headers = request.headers;
	var host = headers.host;
	var path = request.url.replace(/^http\:\/\/[^\/]+/,'');
	host = 'www.baidu.com:80';
	headers.host = host;
	return headers;
}
exports.start = function(port){
	port = port || 2419;
	function httpHander(request,response){
		try{
			var url = request.url.replace(/[#?&].*$/,'');
			if(/^\/--exit$/.test(url)){
				response.writeHead(200, {'x-action-exit':'1','Content-Type': 'text/plain'});
				response.end('closing');
				process.exit(0);
			} else if(/^http\:\/\//.test(url)){
				return onProxy(request,response);
			}else{
				return onRequest(port,response)
			}
		}catch(e){
			console.log(e);
		}
	}
	function complete(){
		console.log('server started on port:'+port);
	}
	var server = require('http').createServer(httpHander);
	server.on('error', function (e) {
		if (e.code == 'EADDRINUSE') {
			console.log("try to exit old server: ");
			require('http').get("http://127.0.0.1:"+port+"/--exit", function(res) {
				if(res.headers['x-action-exit'] == 1){
					setTimeout(function(){
						server.listen(port,complete);
					},2000);
				}else{
					console.log("port used!!" + port);
				}
			}).on('error', function(e) {
				console.log("got error: " + e.message);
				//server.listen(port,complete);
			});
		}
	});
	server.listen(port,complete);
}
