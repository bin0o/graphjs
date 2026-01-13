const fs = require('fs')

function f( string) {
    const ola = {x: string};

    fs.writeFileSync("teste.txt", JSON.stringify(ola));
}

function read() {
    var data = fs.readFileSync("teste.txt", 'utf8');
    eval(data)
}

// f("teste.txt","mafalda");
// read("teste.txt");