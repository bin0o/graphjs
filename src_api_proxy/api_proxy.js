var Path  = require('path');
var FS = require('fs');
exports.writeStatic = function writeStatic(request, response,callback) {
	var root = Path.resolve(
		require.resolve('api-proxy/lib/static.js'),
		'../../www'
	);
	
	var url = request.url.replace(/[?#][\s\S]*/,'');
	var filepath = Path.join(root,url);
	//console.log(filepath)
	
	//console.info('request:',url)
	FS.stat(filepath,function(error,stats){
	    if(stats && stats.isDirectory()){
	    	return writeDir(request,response,filepath);
	    }
	    if(stats && !error){
	    	writeFile(request,response,filepath);
	    }else{
	    	callback(request,response);
	    	//writeNotFound(filepath,response,"resource not found"); 
	    }
	});
}

function writeContent(request,response,url,text){
	var contentType = guessContentType(filepath);
	var expires = new Date(+new Date + 1000 *1)
	var headers = {'Content-Type' : contentType,"Expires":expires.toGMTString(),"Cache-Control": +expires}
	response.writeHead(200, headers);
	response.write(text);
    response.end();    
}
function writeFile(request,response,filepath){
	var contentType = guessContentType(filepath);
     response.writeHead(200, {"Content-Type": contentType});
     FS.readFile(filepath,'binary',
				function(err,tmp){
					response.write(tmp)
					response.end();
				});    
}
function writeNotFound(request,response,filepath,msg){
     response.writeHead(200, {"Content-Type": "text/plain"});    
     response.write("404 Not Found \n filepath:"+filepath+'\n'+(msg||''));    
     response.end();    
}

function writeDir(request,response,filepath){
	var url = request.url;
	var purl = url.replace(/[?].*$/,'')
	if(/\/$/.test(purl)){
		FS.readdir(filepath, function(err, files) {  
     		response.writeHead(200, {"Content-Type": "text/html;charset=UTF-8"}); 
			FS.readFile(require.resolve('api-proxy/lib/index.html'),'utf-8',
				function(err,tmp){
					var buf = []
					for(var i=0;i<files.length;i++){
						var file = files[i];
						buf.push("<div class='file-row'><a href='",file,"'>",file,'</a></div>\n');
					}
					tmp = tmp.replace('$!{dir}',filepath).replace('$!{content}',buf.join(''));
					response.write(tmp,'utf-8')
					response.end();
				});
		});
	}else{
		response.writeHead(301, {"Location" : purl+'/' + url.substring(purl.length)});    
	            	response.end();    
	}
}


function guessContentType(url){
	var type = url.replace(/^.*\.(\w+)(?:[;?#].*)?$/,'$1').toLowerCase();
	switch(type){
	case 'htc':
		//type = 'text/x-component';
		type = "application/octet-stream"
		break;
	case 'js':
		type = 'text/javascript;charset=utf-8'
		break;
	case 'css':
		type = 'text/css;charset=utf-8'
		break;
	case 'html':
	case 'htm':
		type = 'text/html;charset=utf-8'
		break;
	case 'jpg':
		type = 'jpeg';
	case 'png':
	case 'gif':
	case 'jpeg':
		type = 'image/'+type;
		break;
	default:
		console.log('unknow:' ,type)
		type = 'text/html;charset=utf-8'
	}
	return type;
}