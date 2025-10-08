import yargs = require("yargs/yargs");
import fs = require("fs");
import path = require("path");
import espree = require("espree")
import escodegen from "escodegen";
import dependencyTree from "dependency-tree";
import { Program } from 'estree';

import { normalizeScript } from "./traverse/normalization/normalizer";
import buildAST from "./traverse/ast_builder";
import { buildCallGraph } from "./traverse/cg_builder";
import { buildCFG, type CFGraphReturn } from "./traverse/cfg_builder";
import { constructExportedObject, findCorrespondingFile, printDependencyGraph, retrieveFunctionGraph } from "./utils/multifile";
import { getFunctionName } from "./traverse/dependency/utils/nodes";
import { readConfig, type Config } from "./utils/config_reader";
import { Graph } from "./traverse/graph/graph";
import { buildPDG, type PDGReturn } from "./traverse/dependency/dep_builder";
import { type GraphNode } from "./traverse/graph/node";
import { type GraphEdge } from "./traverse/graph/edge";
import { DependencyTracker } from "./traverse/dependency/structures/dependency_trackers";
import { OutputManager } from "./output/output_strategy";
import { DotOutput } from "./output/dot_output";
import { CSVOutput } from "./output/csv_output";
import { printStatus } from "./utils/utils";

// Generate the program graph (AST + CFG + CG + PDG)
function parse(filename: string, config: Config, fileOutput: string, silentMode: boolean, nodeCounter: number,
    edgeCounter: number): [Graph, DependencyTracker] {
    try {
        var modulePath = filename.substring(0, filename.lastIndexOf('/'))
        if (isNodeModule(filename) && !nodeModuleMainMap.has(modulePath)) {
            const mainFile = getMainFileOfModule(modulePath);
            if (mainFile) {
                nodeModuleMainMap.set(mainFile[1], mainFile[0]);
            }
        }

        // Skip only non-JS (keep .js, .mjs, .cjs)
        const ext = path.extname(filename);
        if (!['.js', '.mjs', '.cjs'].includes(ext)) {
            throw new Error(`Unsupported extension for parser: ${ext}`);
        }

        let fileContent: string = fs.readFileSync(filename, "utf8");
        // Remove shebang line
        if (fileContent.slice(0, 2) === "#!") fileContent = fileContent.replace(/^#!(.*\r?\n)/, '\n')

        // Decide sourceType per file (ESM vs CJS)
        const sourceType = resolveSourceType(filename, fileContent);

        // Parse AST
        const ast = espree.parse(fileContent, {
            ecmaVersion: 'latest',
            sourceType, // <-- per-file type
            loc: true
        }) as unknown as Program;
        //const ast = esprima.parseModule(fileContent, { loc: true, tolerant: true });
        !silentMode && printStatus("AST Parsing");

        // Normalize AST
        const normalizedAst = normalizeScript(ast);
        !silentMode && printStatus("AST Normalization");

        // Generate the normalized code, to store it
        const code = escodegen.generate(normalizedAst);
        !silentMode && console.log(`\nNormalized code:\n${code}\n`);
        if (fileOutput) fs.writeFileSync(fileOutput, code);

        // Build AST graph
        const astGraph = buildAST(normalizedAst, nodeCounter, edgeCounter, filename);
        !silentMode && printStatus("Build AST");

        // Build Control Flow Graph (CFG)
        const cfGraphReturn: CFGraphReturn = buildCFG(astGraph);
        !silentMode && printStatus("Build CFG");

        // Build Call Graph (CG)
        const callGraphReturn = buildCallGraph(cfGraphReturn.graph, cfGraphReturn.functionContexts, config);
        !silentMode && printStatus("Build CG");
        const callGraph = callGraphReturn.callGraph;
        config = callGraphReturn.config;

        // Build Program Dependence Graph (PDG)
        const pdgReturn: PDGReturn = buildPDG(callGraph, cfGraphReturn.functionContexts, config);
        !silentMode && printStatus("Build PDG");
        const pdgGraph = pdgReturn.graph;
        const trackers = pdgReturn.trackers;

        // Print trackers
        !silentMode && trackers.print();

        // Return the pdg graph and trackers
        return [pdgGraph, trackers];
    } catch (e: any) {
        console.log("Error:", e.stack);
    }

    return [new Graph(null), new DependencyTracker(new Graph(null), new Map<number, number[]>())];
}

// Choose ESM/CJS per file
function resolveSourceType(filePath: string, fileContent: string): 'module' | 'script' {
    const ext = path.extname(filePath);
    if (ext === '.mjs') return 'module';
    if (ext === '.cjs') return 'script';

    // For .js follow nearest package.json type, then heuristics
    const pkgType = findNearestPackageType(path.dirname(filePath));
    if (pkgType === 'module') return 'module';

    // Heuristic: look for top-level import/export
    // (cheap, good enough; the normalizer will run afterward)
    const seemsESM = /^\s*(import\s+[\s\S]+?from\s+|import\s*\(|export\s)/m.test(fileContent);
    return seemsESM ? 'module' : 'script';
}

function findNearestPackageType(dir: string): 'module' | 'commonjs' | null {
    try {
        let curr = dir;
        while (curr && curr !== path.dirname(curr)) {
            const pkgPath = path.join(curr, 'package.json');
            if (fs.existsSync(pkgPath)) {
                const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
                if (pkg && typeof pkg.type === 'string') {
                    return pkg.type === 'module' ? 'module' : 'commonjs';
                }
                return null;
            }
            curr = path.dirname(curr);
        }
    } catch { /* ignore */ }
    return null;
}

function isNodeModule(dep: string): boolean {
    return dep.includes("node_modules/")
}


function getMainFileOfModule(moduleName: string): [string, string] | null {
    try {
        const parts = moduleName.split("node_modules/");
        const package1 = parts[1].split("/")

        if (parts.length < 2 || (package1.length > 1 && !package1.includes("src"))) return null;

        const modulePath = path.join(parts[0],"node_modules",package1[0])
        const module = path.basename(modulePath)

        const pkgPath = path.join(modulePath, "package.json");
        const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
        const mainFile = pkg.main || "index.js";
        const resolvedMain = path.resolve(modulePath, mainFile);
        return [resolvedMain, module];
    } catch (e: any) {
        console.warn(`Failed to resolve main file for module "${moduleName}":`, e.message);
        return null;
    }
}

// Traverse the dependency tree of the given file and generate the code property graph that accounts for all the dependencies
function traverseDependencyGraph(depGraph: any, config: Config, normalizedOutputDir: string, silentMode: boolean): Graph {
    function traverse(currFile: string, depGraph: any, config: Config, normalizedOutputDir: string, silentMode: boolean,
        exportedObjects: Map<string, Object>, nodeCounter: number, edgeCounter: number): [Graph, number, number, DependencyTracker] {
        let trackers: DependencyTracker;
        let cpg = new Graph(null);
        for (const [file, childDepGraph] of Object.entries(depGraph)) { // first parse its dependencies
            // skip empty dependencies or already parsed files
            const ext = path.extname(file);
            if (exportedObjects.has(file) || (ext !== ".js" && ext !== ".cjs" && ext !== ".mjs")) continue;
            [cpg, nodeCounter, edgeCounter, trackers] = traverse(file, childDepGraph, config, normalizedOutputDir, silentMode, exportedObjects, nodeCounter, edgeCounter);
        }

        // parse the file and generate the exported Object
        [cpg, trackers] = parse(currFile, config, path.join(normalizedOutputDir, path.basename(currFile)), silentMode,
            nodeCounter, edgeCounter);
        nodeCounter = cpg.number_nodes;
        const exported = constructExportedObject(cpg, trackers);

        // add the exported objects to the map
        const dir = path.dirname(currFile);
        exportedObjects.set(currFile, exported);
        exportedObjects.set(currFile.slice(0, -3), exported); // remove the .js extension (it might be referenced without it)

        // map that stores the function that a function returns
        // the map would store the identifier of the variable node has the key and the pair [*module name*,*function of module name*] has value of the key
        // e.g. const middleware = helper.createMiddleware() would be {"middleware": [helper, createMiddleware]}
        const returnedFunctionMap = new Map<string |null|undefined, string[]>()

        // add the exported functions to cpg to generate the final graph
        trackers.callNodesList.forEach((callNode: GraphNode) => {
            const { calleeName, functionName } = getFunctionName(callNode);

            let [module, propertiesToTraverse] = findCorrespondingFile(calleeName, callNode.functionContext, trackers);
            propertiesToTraverse.push(functionName);

            // module being undefined may mean that a variable without module (middleware) is being called because it holds a functionFactory
            // e.g. const middleware = helper.createMiddleware()
            if (module === undefined){
                for (const [key, value] of returnedFunctionMap.entries()) {
                    // if the returnNode identifier (key) includes the functionName it means that this variable holds a functionFactory
                    if (key?.includes(functionName)){
                        // use the stored values so the functionFactory node is used
                        module = value[0];
                        propertiesToTraverse.pop()
                        propertiesToTraverse.push(value[1])
                        break;
                    }
                }
            }

            if (module) { // external call
                let originalNodeModuleName = null
                if (nodeModuleMainMap.has(module)){
                    originalNodeModuleName = module
                    module = nodeModuleMainMap.get(module)
                }
                else {
                    module = path.join(dir, module);
                }
                var exportedObj:any = [];
                if (module){
                    exportedObj = exportedObjects.get(module);
                }

                if (!exportedObj || Object.keys(exportedObj).length === 0) return;

                const funcGraph: GraphNode | undefined = retrieveFunctionGraph(exportedObj, propertiesToTraverse);

                if (funcGraph) {
                    // store the function that the funcGraph node returns because that is the function that the code will run
                    // e.g. function createMiddleware() {  
                    //          return (req, res) => {
                    //              handle(req)
                    //          }
                    //      }
                    const trueFuncGraph = funcGraph.returns ?? funcGraph;

                    if (funcGraph.returns) {
                        const returnEdge = callNode.edges.find(
                        e => e.type === "PDG" && e.label === "RET"
                        );
        
                        if (returnEdge) {
                            // retrieve the identifier of the node where the function is being assigned to
                            // e.g. const middleware = helper.createMiddleware(), in thus example the returnNode is the node related to middleware
                            const returnNode = returnEdge.nodes.find( 
                                n=> n.type === "PDG_OBJECT"
                            )
                            // This function returns another function
                            const functionFactory = [];
                            // store the values in the map
                            if (module){
                                functionFactory.push(path.basename(originalNodeModuleName ?? module),functionName)
                            }
                            returnedFunctionMap.set(returnNode?.identifier,functionFactory)
                        }
                    }   

                    // Use the final resolved function (original or returned) for CG/ARG construction
                    cpg.addExternalFuncNode(`function ${module}.${trueFuncGraph.identifier ?? ""}`, trueFuncGraph);

                    const params = trueFuncGraph.edges
                        .filter((e: GraphEdge) => e.label === "param")
                        .map((e: GraphEdge) => e.nodes[1]);

                    // connect object arguments to the parameters of the external function
                    callNode.argsObjIDs.forEach((args: number[]) => {
                        args.forEach((arg: number, index) => {
                            if (arg !== -1 && params[index + 1]) { // if the argument is a constant its value is -1 (thus literals aren't considred here)
                                cpg.addEdge(arg, callNode.id, { type: "PDG", label: "ARG", objName: params[index + 1].identifier });
                            }
                        });
                    });

                    cpg.addEdge(callNode.id, trueFuncGraph.id, { type: "CG", label: "CG" });
                }
            }
        });

        edgeCounter = cpg.number_edges;

        return [cpg, nodeCounter, edgeCounter, trackers];
    }

    const [cpg, nodeCounter, edgeCounter, trackers] = traverse(Object.keys(depGraph)[0], depGraph, config, normalizedOutputDir, silentMode, new Map<string, Object>(), 0, 0);

    trackers.addTaintedNodes();

    return cpg;
}

// Parse program arguments
const argv = yargs(process.argv.slice(2))
    .usage('Usage: $0 <command> [options]')
    // JavaScript file to be analyzed
    .option('f', { alias: 'file', nargs: 1, desc: 'Load a JavaScript file', type: 'string', demandOption: true })
    // Location of the config file
    .option('c', { alias: 'config', nargs: 1, desc: 'Load a config file', type: 'string', default: '../../config.json' })
    // Location of the graph output directory (csv and svg files)
    .option('o', { alias: 'output', nargs: 1, desc: 'Specify the output directory', type: 'string', demandOption: true })
    // Select if graph figure should be generated (use arg --graph to generate)
    .option('graph', { desc: 'Output the graph figure', type: 'boolean' })
    // Select if csv files should be generated (use arg --csv to generate)
    .option('csv', { desc: 'Output the graph csv files', type: 'boolean' })
    // Select graph structures to not show in the final graph figure (use -i AST to ignore AST)
    .option('i', { alias: 'ignore', desc: 'Set array of structures to ignore in graph figure', type: 'array', implies: 'graph' })
    // Select functions to not show in the final graph figure
    .option('if', { alias: 'ignore_func', desc: 'Set array of functions to ignore in graph figure', type: 'array', implies: 'graph' })
    // Select if code should be displayed in each graph statement (otherwise AST values are shown)
    .option('sc', { alias: 'show_code', desc: 'Show the code in each statement in graph figure', type: 'boolean', implies: 'graph' })
    // Select to run in silent mode
    .option('silent', { desc: 'Silent mode (not verbose)', type: 'boolean' })
    // Examples
    .example('$0 -f ./foo.js -c ../config.json', 'process the foo.js file using the config.json options')
    .example('$0 -f ./foo.js -c ../config.json -i="AST"', 'process the foo.js file using the config.json options')
    .example('$0 -f ./foo.js -c ../config.json -if="__main__"', 'process the foo.js file using the config.json options')
    .help('h').alias('h', 'help').parseSync();

const filename: string = argv.file as string;
const configFile: string = path.resolve(__dirname, argv.config as string);
const silentMode: boolean = argv.silent ?? false;
const normalizedPath: string = `${path.join(argv.o, 'normalized.js')}`;

const nodeModuleMainMap: Map<string, string> = new Map();

// If silent mode is selected, do not show error traces
if (silentMode) console.trace = function () {};

// Verify arguments
if (!fs.existsSync(filename)) console.error(`${filename} is not a valid file.`);
if (!fs.existsSync(configFile)) console.error(`${configFile} is not a valid config file.`);

// Generate code property graph
const config = readConfig(configFile);

const depTree = dependencyTree({
    filename,
    directory: path.dirname(filename)
});

const graph = traverseDependencyGraph(depTree, config, path.dirname(normalizedPath), silentMode);

if (!graph) console.error(`Unable to generate code property graph`);

// Generate output files
const graphOptions = { ignore: argv.i ?? [], ignore_func: argv.if ?? [], show_code: argv.sc ?? false };

if (argv.csv) {
    graph.outputManager = new OutputManager(graphOptions, new CSVOutput());
    graph.output(argv.o);
}

if (argv.graph) {
    graph.outputManager = new OutputManager(graphOptions, new DotOutput());
    graph.output(argv.o);
    printDependencyGraph(depTree, path.join(argv.o, 'dependency_graph.txt'));
}

const statsFileName = path.join(argv.o, 'graph_stats.json')
fs.writeFileSync(statsFileName, `{ "edges": ${graph.edges.size}, "nodes": ${graph.nodes.size}}`)
