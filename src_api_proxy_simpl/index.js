const api_proxy = require('./api_proxy');

exports.onRequest = function onRequest(request,response){
	api_proxy.writeStatic(request,response,function(){
		response.writeHead(200, {'Content-Type': 'text/plain'});
		response.end('ok,not found');
	});
}

