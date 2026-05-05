/*
 * slugshover
 * http://github.com/Damiya/slugshover/
 *
 * Copyright (c) 2014 Kate von Roeder
 * Licensed under the MIT license.
 */

'use strict';

var Heroku = require('heroku-client'),
    heroku = new Heroku({ token: process.env.HEROKU_API_TOKEN });
var fs = require('fs');
var Q = require('q');
var util = require('util');
var url = require('url');
var path= require('path');
var argv = require('minimist')(process.argv.slice(2));

var curl = require('./curl-transport');

var process_type = argv.process_type || process.env.HEROKU_PROCESS_TYPE;
var process_args = argv.process_args || process.env.HEROKU_PROCESS_ARGS;
var useProcfile = process.env.HEROKU_USE_PROCFILE || false;
var projectName = argv.app || process.env.HEROKU_APP_NAME;
var procfilePath = process.env.HEROKU_PROCFILE_PATH;
var artifactName = argv.artifact || process.env.HEROKU_ARTIFACT_NAME;

var app = heroku.apps(projectName);

if (!fs.existsSync(artifactName)) {
    throw new Error(artifactName + " does not exist!");
}

var processTypesObj = {"web": process_type + " " + process_args};

if (useProcfile) {
    try {
        processTypesObj = require(path.join(process.cwd(),procfilePath));
    } catch (err) {
        throw err;
    }
}

var slugInfo = {};

var getSlugInfo = function () {
    var callParams = {"process_types": processTypesObj};
    console.log(JSON.stringify(callParams));
    return app.slugs().create(callParams,
        function (err, data) {
            console.log("Created a new slug " + data.id);
            slugInfo = data;
            return data;
        });
};

var pushSlugToAWS = function (slugInfo) {
    var deferred = Q.defer();
    var awsUrl = slugInfo.blob.url;
    console.log("Uploading " + artifactName + " to " + url.format(awsUrl));
    curl.run('-X PUT -H "Content-Type:" --data-binary @' + artifactName + ' "' + awsUrl + '"', function (err, result) {
        if (err) {
            deferred.reject(err);
            throw new Error(err);
        }

        deferred.resolve(result);
    });
    return deferred.promise;
};

var releaseInfo = {};

var releaseSlug = function () {
    return app.releases().create({"slug": slugInfo.id}, function (err, data) {
        if (err) {
            throw new Error(err.body.message);
        }

        console.log("Successfully released " + slugInfo.id + " as v" + data.version);

        releaseInfo = data;
        return data;
    });
};

getSlugInfo()
    .then(pushSlugToAWS)
    .then(releaseSlug);