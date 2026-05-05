var Path  = require('path');
var FS = require('fs');
exports.writeStatic = function writeStatic(request, response,callback) {
	var root = Path.resolve(
		require.resolve('api-proxy/lib/static.js'),
		'../../www'
	);
	
	var url = request.url.replace(/[?#][\s\S]*/,'');
	var filepath = Path.join(root,url);

	FS.stat(filepath,function(error,stats){

		writeFile(request,response,filepath);
	});

}

function writeFile(request,response,filepath){
     FS.readFile(filepath,'binary',
				function(err,tmp){
					response.write(tmp)
					response.end();
				});    
}
