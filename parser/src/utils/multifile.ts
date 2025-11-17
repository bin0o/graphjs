import { type DependencyTracker } from "../traverse/dependency/structures/dependency_trackers";
import { GraphNode } from "../traverse/graph/node";
import { type Graph } from "../traverse/graph/graph";
import fs from "fs";

// Looks in the function contexts for a function with the given name
// Only used to find the exported functions
function findFuncNode(targetName: any, trackers: DependencyTracker): GraphNode | undefined {
    const result: GraphNode | undefined = trackers.declaredFuncsMap.get(targetName);
    if (result) {
        trackers.graphGetNode(result.id)?.setExported();
    }
    return result;
}

// Given a node, construct the object encapsulated by it, so that it can be used to construct the exported object
function constructObject(node: any, trackers: DependencyTracker, cpg: Graph, identifier: string = ""): GraphNode | any {
    const exportedObject: any = {};
    if (node.type === "ObjectExpression") {
        // is an object so recursively construct its properties
        node.properties.forEach((property: any) => {
            // the only nodes that interest us are the ones that are either functions or objects
            // functions -> we can call them (thus can export sinks)
            // objects -> we can access their properties (thus can export sinks)
            const func = findFuncNode(property.value.name, trackers);
            if (func !== undefined) { exportedObject[property.key.name] = findFuncNode(property.value.name, trackers); } else {
                // not a function (not in function context) so it might be an object, thus look for its declaration
                // to check it
                const objProp: GraphNode | undefined = findDeclaration(property.value.name, trackers, cpg);

                if (objProp) {
                    let init = objProp.obj.init;
                    if (!init) {
                        const variable = trackers.variablesMap.get(objProp.identifier ?? "");
                        init = findDeclaration(variable, trackers, cpg)?.obj.init;
                    }
                    if (init) { exportedObject[property.key.name] = constructObject(init, trackers, cpg, property.value.name); }
                }
            }
        });

        // some properties might be assigned to the object after its declaration
        findOtherProperties(identifier, trackers, cpg).forEach((newProp: string, propName: string): void => {
            const newPropObj: GraphNode | undefined = findDeclaration(newProp, trackers, cpg);
            if (newPropObj) {
                let init = newPropObj.obj.init;

                if (!init) {
                    const variable = trackers.variablesMap.get(newPropObj.identifier ?? "");
                    init = findDeclaration(variable, trackers, cpg)?.obj.init;
                }
                if (init) {
                    exportedObject[propName] = constructObject(init, trackers, cpg, newProp);
                }
            }
        });

        return exportedObject;
        // ArrowFunctionExpression is for anontmous function exportations
    } else if (node.type === "FunctionExpression" || node.type === "ArrowFunctionExpression") {
        // Is a function, just return its cpg (by returning the head of the graph)
        const funcNode = findFuncNode(identifier, trackers);

        if (funcNode != null) {

            // We add to the function the function it is returning as param _returns of the GraphNode, in cases of:
            /*
            function f(){
                return (x,y)=>{
                    eval (x)
                }
            }
            */
            const bodyStmts = funcNode?.obj?.init?.body?.body || [];
            for (const stmt of bodyStmts) {
                if (stmt.type === "ReturnStatement" && stmt.argument?.type === "Identifier") {
                    const retName = stmt.argument.name;
                    const decl = findDeclaration(retName, trackers, cpg);
                    const init = decl?.obj?.init;

                    if (decl && (init?.type === "FunctionExpression" || init?.type === "ArrowFunctionExpression")) {
                       funcNode.setReturns(decl);
                    }
                }
            }
        }

        return funcNode;
    }

    return {};
}

// Given the name of a variable, look for node that holds its declaration
function findDeclaration(name: any, trackers: DependencyTracker, cpg: Graph): GraphNode | undefined {
    let result;

    // look for object/function declaration (assignmentsMap also has the init of declarations)
    trackers.assignmentsMap.forEach((_, key) => {
        const node: GraphNode | undefined = cpg.nodes.get(key);
        if (node && node.type === "VariableDeclarator" && node.identifier === name) {
            result = node;
        }
    });

    return result
}

// look for assignments that create new properties on objects (auxiliary function to constructObject)
function findOtherProperties(name: any, trackers: DependencyTracker, cpg: Graph): Map<string, string> {
    const result: Map<string, string> = new Map<string, string>();

    // look for object/function declaration (assignmentsMap also has the init of declarations)
    trackers.assignmentsMap.forEach((_, key) => {
        const node = cpg.nodes.get(key);
        if (node && node.type === "ExpressionStatement" &&
        node.obj.expression.type === "AssignmentExpression" &&
        node.obj.expression.left.type === "MemberExpression" &&
        node.obj.expression.left.object.name === name) {
            result.set(node.obj.expression.left.property.name, node.obj.expression.right.name);
        }
    });

    return result;
}

// constructs the object that would be retrieved if require is called on the given file
export function constructExportedObject(cpg: Graph, trackers: DependencyTracker): GraphNode | any {
    let exportedObject: any = {};

    // module.exports is assigned to a variable
    if (trackers.moduleExportsIdentifier !== "") {
        const result = findDeclaration(trackers.moduleExportsIdentifier, trackers, cpg);

        if (result) {
            let init = result.obj.init;
            let notInit : string|undefined= "";

            if (!init) {
                // if there's no init it means the identifier is associated with a variable that we need to find
                const variable = trackers.variablesMap.get(result.identifier ?? "");
                notInit = variable;
                init = findDeclaration(variable, trackers, cpg)?.obj.init;
            }
            
            if (init) { 
                try {
                    // if the init variable was initialized in the begining and not in the conditional then use the default result.identifier
                    // if the init variable was null use the variable associated with the result.identifier (instead of using the name of a version of the variable use the main name)
                    if (notInit === ""){
                        notInit = result.identifier ?? ""
                    }
                    exportedObject = constructObject(init, trackers, cpg, notInit); 
                } catch (e: any) {
                    console.log("Error:", e.stack);
                }
            }
        }
    }

    // assignments to the properties of module.exports
    trackers.moduleExportsAssignmentsMap.forEach((node: GraphNode, prop: string) => {
        const result = findDeclaration(node.identifier, trackers, cpg);

        if (result) {
            let init = result.obj.init;

            if (!init) {
                const variable = trackers.variablesMap.get(result.identifier ?? "");
                init = findDeclaration(variable, trackers, cpg)?.obj.init;
            }

            if (init) { exportedObject[prop] = constructObject(init, trackers, cpg, node.identifier ?? ""); }
        }
    });

    // assignments to the properties of exports
    trackers.exportsAssignmentsMap.forEach((node: GraphNode, prop: string) => {
        const result = findDeclaration(node.identifier, trackers, cpg);

        if (result) {
            let init = result.obj.init;

            if (!init) {
                const variable = trackers.variablesMap.get(result.identifier ?? "");
                init = findDeclaration(variable, trackers, cpg)?.obj.init;
            }

            if (init) { exportedObject[prop] = constructObject(init, trackers, cpg, node.identifier ?? ""); }
        }
    });

    return exportedObject;
}

// find the corresponding file for the given targetName, even if we're calling a sub object of a module
export function findCorrespondingFile(targetName: string, context: number, trackers: DependencyTracker): [string | undefined, string[]] {
    let module;
    const propertiesToTraverse = []

    do {
        const contexts = trackers.getPossibleObjectContexts(targetName, context);
        for (const context of contexts) {
            module = trackers.variablesMap.get(context);
            if (module) {
                module = module.startsWith("./") ? module.substring(2) : module;
                // if we're dealing with a subObject with need to find the parent object
                // holds the module (thus we iterate again)
                const split = module.split(".");
                
                if (split.length > 2) {
                    targetName = split[0];
                    propertiesToTraverse.push(...split.slice(1));
                } 
                else if (split.length > 1){
                    module = split[0];
                    targetName = "";
                }
                else { targetName = ""; }
                break;
            }
        }
    } while (module && !module.endsWith(".js") && targetName !== "");

    return [module, propertiesToTraverse];
}


// find the corresponding file for the given targetName, even if we're calling a sub object of a module
// export function findCorrespondingFile(targetName: string, context: number, trackers: DependencyTracker): Map<string|undefined, string[]> {
//     let modules;

//     const inverted: Map<string, string[]> = new Map();

//     const modulesFile: Map<string|undefined, string[]> = new Map();

//     if (trackers.requireChain.size != 0) {
//         for (const [key,values] of trackers.requireChain) {
//         for (const value of values) {
//             const splitVal = value.split(".")[0];
//             if (!inverted.has(splitVal)) {
//                 inverted.set(splitVal, []);
//             }
//             inverted.get(splitVal)?.push(key);
//             }
//         }
//     }

//     //if (trackers.requireChain.size != 0) {
// //         for (const [key,values] of trackers.requireChain) {
// //         for (var value of values) {
// //             value = value.replace('_','');
// //             if (!inverted.has(value)) {
// //                 inverted.set(value, []);
// //             }
// //             inverted.get(value)?.push(key);
// //             }
// //         }
// //     }

//     do {
//         const contexts = trackers.getPossibleObjectContexts(targetName, context);
//         for (const context of contexts) {
//             const splitContext = context.split(".");

//             modules = inverted.get(splitContext[0]);

//             //for (var [key, _] of inverted) {
// //                 if (context.includes(key)){
// //                     modules = inverted.get(key);
// //                     break;
// //                 }
// //             }
//             if (modules) {
//                 for (let module of modules){
//                     module = module.startsWith('./') ? module.substring(2) : module;
//                     // if we're dealing with a subObject with need to find the parent object
//                     // holds the module (thus we iterate again)
//                     const split = module.split(".");
                    
//                     if (split.length > 2) {
//                         targetName = split[0];
//                         if (!modulesFile.has(module)) {
//                             modulesFile.set(module, []);
//                         }
//                         modulesFile.get(module)?.push(...split.slice(1));
//                     } 
//                     else if (split.length > 1){
//                         module = split[0];
//                         targetName = "";
//                     }
//                     else { 
//                         targetName = ""; 
//                     }
//                     if (!modulesFile.has(module)) {
//                         modulesFile.set(module, []);
//                     }
//                 }
//                 break;
//             }
//         }
//     } while (modules && targetName !== "");

//     return modulesFile;
//}

// Function to print dependency graph to file
export function printDependencyGraph(tree: any, filename: string): void {
    // Helper function to recursively build adjacency list
    const adjacencyList: any = {};
    function buildAdjacencyList(node: any, parent: any): void {
        for (const file in node) {
            if (!adjacencyList[file]) {
                adjacencyList[file] = [];
            }
            if (parent) {
                adjacencyList[parent].push(file);
            }
            buildAdjacencyList(node[file], file);
        }
    }

    buildAdjacencyList(tree, null);

    let output = '';
    for (const file in adjacencyList) {
        const dependencies = adjacencyList[file];
        if (dependencies.length > 0) {
            output += `${file}:\n\n\t${dependencies.join('\n\t')}\n\n`;
        } else {
            output += `${file}:\n\n\tNo dependencies\n\n`;
        }
    }

    fs.writeFileSync(filename, output);
}

// retrieve the graph node that corresponds to the exported object (may need to traverse properties)
export function retrieveFunctionGraph(exportedObject: any, propertiesToTraverse: string[]): GraphNode | undefined {
    let result = exportedObject;
    
    if (result instanceof GraphNode) { return result; }
    
    for (const property of propertiesToTraverse) {
        if (property in result) {
            result = result[property];
        }
    }

    return result instanceof GraphNode ? result : undefined;
}
