from .interaction_protocol import interaction_protocol
from .my_utils import utils as my_utils
import json

from .query import Query


class Injection:
	intra_injection_query = f"""
		MATCH
			(source:TAINT_SOURCE)
				-[param_edge:PDG]
					->(param:PDG_OBJECT)
						-[pdg_edges:PDG*1..]
							->(sink:TAINT_SINK),
			(source_cfg)
				-[param_ref:REF]
					->(param),
			(source_cfg)
				-[:AST]
					->(source_ast),
			(sink_cfg)
				-[:SINK]
					->(sink),
			(sink_cfg)
				-[:AST]
					->(sink_ast)
		WHERE
			param_edge.RelationType = "TAINT" AND
			param_ref.RelationType = "param"
		RETURN *
	"""

	bottom_up_greedy_injection_query = f"""
		MATCH (func:VariableDeclarator)-[ref_edge:REF]->(param:PDG_OBJECT)
WHERE ref_edge.RelationType = "param"

CALL apoc.path.expandConfig(param, {{
  relationshipFilter: "RET>|DEP>|NV>|ARG>|SO",
  labelFilter: "+PDG_OBJECT|+PDG_CALL|/TAINT_SINK",
  minLevel: 1,
  maxLevel: 15,
  uniqueness: "NODE_PATH",
  bfs: true,
  filterStartNode: false
}}) YIELD path

WITH func, param, path,
     last(nodes(path)) AS sink,
     relationships(path) AS rels
WHERE sink:TAINT_SINK
  AND ALL(r IN rels WHERE type(r) <> "ARG" OR r.valid = true)

MATCH (sink_cfg)-[:SINK]->(sink)
MATCH (sink_cfg)-[:AST]->(sink_ast)

WITH func, param, sink, sink_cfg, sink_ast, collect(path) AS paths
RETURN func, param, sink, sink_cfg, sink_ast, paths
		"""

	# Cache the taint propagation information
	callInfo = {}

	def __init__(self, query: Query):
		self.query = query

	def find_vulnerable_paths(self, session, vuln_paths, source_file, filename: str, detection_output, query_type, config):
		print(f'[INFO] Running injection query.')
		self.query.start_timer()
		detection_results = []

		# Run query based on type
		if query_type == 'intra':
			results = session.run(self.intra_injection_query)
		elif query_type == 'bottom_up_greedy':
			results = session.run(self.bottom_up_greedy_injection_query)
		else:
			results = []

		vuln_path_distincts = []
		for record in results:
			if query_type == "intra" or query_type == "bottom_up_greedy":
				if query_type == "bottom_up_greedy":
					confirmed, paramId = self.query.confirm_vulnerability(session, record["func"]["Id"], record["param"])
					if not confirmed:
						continue

					self.paramIdentifier = f"""
						MATCH (func:VariableDeclarator)-[edge:REF]->(param:PDG_OBJECT)
							WHERE param.Id = \"{paramId}\" AND edge.RelationType = "param"
						MATCH (func)-[func_edge:AST]->(func_ast)-[ast_edge:AST]->(param_ast)
						WHERE ast_edge.RelationType = "param" AND func_edge.RelationType = "init"

						WITH param_ast, param,

						split(reduce(s = "", p IN split(param.IdentifierName, '.')[1..] |
						CASE WHEN s = "" THEN p ELSE s + "." + p END),'-')[0] AS param_name
						WHERE edge.RelationType = "param"
						AND param_ast.IdentifierName = param_name

						RETURN param_ast
					"""
					param_ast_result = session.run(self.paramIdentifier)

					if param_ast_result.peek() is None:
						continue
					
					
					param_ast = param_ast_result.single()["param_ast"]

				sink_name = record["sink"]["IdentifierName"]
				sink_lineno = json.loads(record["sink_ast"]["Location"])["start"]["line"]
				file = json.loads(record["sink_ast"]["Location"])["fname"]
				sink_file = my_utils.get_code_line_from_file(file, sink_lineno)
				source_name = param_ast["IdentifierName"]
				source_lineno = json.loads(param_ast["Location"])["start"]["line"]
				source_param_file = json.loads(param_ast["Location"])["fname"]
				source_param = my_utils.get_code_line_from_file(source_param_file, source_lineno)
				vuln_type: str = my_utils.get_injection_type(sink_name, config)
				vuln_path_distinct = {
					"filename": file,
					"vuln_type": vuln_type,
					"sink": sink_file,
					"sink_lineno": sink_lineno,
					"sink_function": record["sink_cfg"]["Id"]
				}

				vuln_path = {
					"filename": file,
					"source" : {
						"name": source_name,
						"code": source_param,
						"lineno": source_lineno,
						"file": source_param_file
					},
					"sink": {
						"name": sink_name,
						"code": sink_file,
						"lineno": sink_lineno,
						"file": file
					},
					"vuln_type": vuln_type,
					"sink_function": record["sink_cfg"]["Id"]
				}
				my_utils.save_intermediate_output(vuln_path, detection_output)
				if not self.query.reconstruct_types and vuln_path_distinct not in vuln_path_distincts:
					vuln_paths.append(vuln_path)
					vuln_path_distincts.append(vuln_path_distinct)
				elif self.query.reconstruct_types and vuln_path_distinct not in vuln_path_distincts:
					detection_results.append(vuln_path)
					vuln_path_distincts.append(vuln_path_distinct)
		self.query.time_detection("injection")

		if self.query.reconstruct_types:
			print(f'[INFO] Reconstructing attacker-controlled data.')
			for detection_result in detection_results:
				vulnerabilities = interaction_protocol.get_vulnerability_info(session, detection_result, source_file, config)
				for detection_obj in vulnerabilities:
					if detection_obj not in vuln_paths:
						vuln_paths.append(detection_obj)
			self.query.time_reconstruction("injection")
		self.initial_format= """
			MATCH (a)-[r]->(b)
			WHERE type(r) IN ["RET","SO","NV","ARG","DEP","TAINT","UNKNOWN"]
			CALL apoc.create.relationship(a, "PDG", properties(r), b) YIELD rel
			// make sure the legacy property exists and matches the relationship kind
			SET rel.RelationType = coalesce(rel.RelationType, type(r))
			RETURN count(rel) AS createdPDG
			"""
		session.run(self.initial_format)
		self.delete_temporary_rels = """
			MATCH ()-[r]->()
			WHERE type(r) IN ["RET","SO","NV","ARG","DEP","TAINT","UNKNOWN"]
			DELETE r
			"""
		session.run(self.delete_temporary_rels)
		return vuln_paths
	