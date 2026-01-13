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
		MATCH
			(func:VariableDeclarator)-[ref_edge:REF]->(param:PDG_OBJECT)
		WHERE
			ref_edge.RelationType = "param"

		OPTIONAL MATCH
			(param)-[edges:PDG*1..]->(sink_direct:TAINT_SINK)
		WHERE
			ALL(edge IN edges WHERE NOT edge.RelationType = "ARG" OR edge.valid = true)

		OPTIONAL MATCH	
			(param)-[edges4:PDG*0..5]->(paramProp:PDG_OBJECT)-[edge1:PDG]->(obj:PDG_OBJECT) 
				WHERE ALL(edge4 in edges4 WHERE NOT edge4.RelationType = "ARG" OR edge4.valid=True) AND edge1.RelationType = "DEP"

		OPTIONAL MATCH 
			(obj)-[edges1:PDG*1..5]-(objSONV:PDG_OBJECT) 
				WHERE ALL( edge1 in edges1 WHERE edge1.RelationType in ["SO","NV"] OR edge1.valid = true)

			WITH obj, sink_direct, func, param, objSONV,
			
				split(reduce(s = "", p IN split(objSONV.IdentifierName, '.')[1..] |
				CASE WHEN s = "" THEN p ELSE s + "." + p END),'-')[0] AS taintedObjName,

				split(reduce(s = "", p IN split(obj.IdentifierName, '.')[1..] |
				CASE WHEN s = "" THEN p ELSE s + "." + p END),'-')[0] AS taintedPropName 

			WHERE objSONV IS NULL OR taintedPropName CONTAINS taintedObjName

			WITH
				coalesce(objSONV, obj) AS obj,
				sink_direct, func, param

		OPTIONAL MATCH 
			(obj)-[edge2:PDG]->(sink_indirect:TAINT_SINK) 

			WHERE edge2.RelationType = "DEP" OR edge2.valid = true

		WITH func, param, [sink_direct, sink_indirect] AS sinks
		UNWIND sinks AS sink
		WITH func, param, sink
		WHERE sink IS NOT NULL

		MATCH
		(sink_cfg)-[:SINK]->(sink),
		(sink_cfg)-[:AST]->(sink_ast)

		RETURN DISTINCT func, param, sink, sink_cfg, sink_ast
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

		for record in results:
			if query_type == "intra" or (query_type == "bottom_up_greedy" and
			self.query.confirm_vulnerability(session, record["func"]["Id"], record["param"])):

				sink_name = record["sink"]["IdentifierName"]
				sink_lineno = json.loads(record["sink_ast"]["Location"])["start"]["line"]
				file = json.loads(record["sink_ast"]["Location"])["fname"]
				sink = my_utils.get_code_line_from_file(file, sink_lineno)
				vuln_type: str = my_utils.get_injection_type(sink_name, config)
				vuln_path = {
					"filename": file,
					"vuln_type": vuln_type,
					"sink": sink,
					"sink_lineno": sink_lineno,
					"sink_function": record["sink_cfg"]["Id"]
				}
				my_utils.save_intermediate_output(vuln_path, detection_output)
				if not self.query.reconstruct_types and vuln_path not in vuln_paths:
					vuln_paths.append(vuln_path)
				elif self.query.reconstruct_types and vuln_path not in vuln_paths:
					detection_results.append(vuln_path)
		self.query.time_detection("injection")

		if self.query.reconstruct_types:
			print(f'[INFO] Reconstructing attacker-controlled data.')
			for detection_result in detection_results:
				vulnerabilities = interaction_protocol.get_vulnerability_info(session, detection_result, source_file, config)
				for detection_obj in vulnerabilities:
					if detection_obj not in vuln_paths:
						vuln_paths.append(detection_obj)
			self.query.time_reconstruction("injection")

		return vuln_paths
	




# def find_vulnerable_paths(self, session, vuln_paths, source_file, filename: str, detection_output, query_type, config):
# 		print(f'[INFO] Running injection query.')
# 		self.query.start_timer()

# 		# decide which queries to run (order matters: intra first)
# 		runs = []
# 		if query_type == 'intra':
# 			runs = [('intra', self.intra_injection_query)]
# 		elif query_type == 'bottom_up_greedy':
# 			runs = [('bottom_up_greedy', self.bottom_up_greedy_injection_query)]
# 		elif query_type == 'both':
# 			runs = [
# 				('intra', self.intra_injection_query),
# 				('bottom_up_greedy', self.bottom_up_greedy_injection_query),
# 			]
# 		else:
# 			return vuln_paths  # unknown type, nothing to do

# 		detection_results = []
# 		# seen signature to avoid duplicates across both queries
# 		# (file, sink_lineno, sink_cfg_id) is a good stable key
# 		seen = set()

# 		for qt, cypher in runs:
# 			results = session.run(cypher)

# 			for record in results:
# 				# keep your original filtering: confirm_vulnerability only for bottom_up
# 				if qt == "bottom_up_greedy" and not self.query.confirm_vulnerability(session, record["func"]["Id"], record["param"]):
# 					continue

# 				sink_name = record["sink"]["IdentifierName"]
# 				sink_loc = json.loads(record["sink_ast"]["Location"])
# 				sink_lineno = sink_loc["start"]["line"]
# 				file = sink_loc["fname"]
# 				sink = my_utils.get_code_line_from_file(file, sink_lineno)
# 				vuln_type: str = my_utils.get_injection_type(sink_name, config)

# 				sig = (file, sink_lineno, record["sink_cfg"]["Id"])
# 				if sig in seen:
# 					continue
# 				seen.add(sig)

# 				# keep query_type tagged so you can see how it was found
# 				vuln_path = {
# 					"filename": file,
# 					"vuln_type": vuln_type,
# 					"sink": sink,
# 					"sink_lineno": sink_lineno,
# 					"sink_function": record["sink_cfg"]["Id"],
# 					"query_type": qt
# 				}

# 				my_utils.save_intermediate_output(vuln_path, detection_output)

# 				if not self.query.reconstruct_types:
# 					if vuln_path not in vuln_paths:
# 						vuln_paths.append(vuln_path)
# 				else:
# 					if vuln_path not in detection_results:
# 						detection_results.append(vuln_path)

# 		self.query.time_detection("injection")

# 		if self.query.reconstruct_types:
# 			print(f'[INFO] Reconstructing attacker-controlled data.')
# 			for detection_result in detection_results:
# 				vulnerabilities = interaction_protocol.get_vulnerability_info(session, detection_result, source_file, config)
# 				for detection_obj in vulnerabilities:
# 					if detection_obj not in vuln_paths:
# 						vuln_paths.append(detection_obj)
# 			self.query.time_reconstruction("injection")

# 		return vuln_paths
