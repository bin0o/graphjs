
function g(x_g,y_g) {
    var z_g = x_g;
    h(x_g,y_g,z_g);
}

function h(x_h,y_h,z_h){
    eval(z_h)
}

module.exports = {g};