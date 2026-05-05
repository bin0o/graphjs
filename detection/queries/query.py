from abc import abstractmethod
import time
from typing import TypedDict, NotRequired


class DetectionResult(TypedDict):
	filename: str
	vuln_type: str
	sink: str
	sink_lineno: int
	sink_function: int
	polluted_obj: NotRequired[object]
	polluting_value: NotRequired[object]


class Query:
	query_types = []
	time_output_file = None
	reconstruct_args = False
	start_time = None

	cgt = {}  # Transposed call graph
	outer_funcs = {}  # Maps a function to its outer function (if it exists)
	paramInfo = {}

	def __init__(self, reconstruct_types, time_output_file):
		self.time_output_file = time_output_file
		self.reconstruct_types = reconstruct_types

	@abstractmethod
	def find_vulnerable_paths(self, session, detection_result: DetectionResult, config):
		pass

	def process_cg(self, session):

		def check_propagation(session, func):
			reaches_return = f"""
				MATCH 
					(func:VariableDeclarator)
						-[:REF]
							->(param:PDG_OBJECT)
								
					WHERE 
						func.Id = \"{func}\"

				CALL apoc.path.expandConfig(param, {{
					relationshipFilter: "RET>|DEP>|NV>|ARG>|SO",
					labelFilter: "+PDG_OBJECT|+PDG_CALL|/PDG_RETURN",
					minLevel: 1,
					maxLevel: 15,
					uniqueness: "NODE_PATH",
					bfs: true,
					filterStartNode: false
					}}) YIELD path

					WITH func, param, path,
						last(nodes(path)) AS return_node,
						relationships(path) AS rels
					WHERE return_node:PDG_RETURN
					AND ALL(r IN rels WHERE type(r) <> "ARG" OR r.valid = true)

				MATCH
					(obj1:PDG_OBJECT)
						-[arg_edge]
							->(call:PDG_CALL)
								-[:CG]
									->(func)

				WHERE
					arg_edge.IdentifierName = param.IdentifierName

				SET arg_edge.valid = true

				RETURN *
			"""

			session.run(reaches_return)

		def process_call_graph(session, cg, start, visited = set()):

			if start in visited:
				return

			visited.add(start)

			if start in cg:
				for callee in cg[start]:
					process_call_graph(session, cg, callee[1], visited)

			check_propagation(session, start)

		set_this_undefined_calls = f"""
			MATCH 
				(arg:PDG_OBJECT)
					-[arg_edge:PDG]
						->(:PDG_CALL)

			WHERE 
				arg_edge.IdentifierName = "this" OR arg_edge.IdentifierName = "undefined"

			SET arg_edge.valid = true
		"""

		session.run(set_this_undefined_calls)

		change_graph = """
			MATCH (a)-[r:PDG]->(b)
			WITH a,b,r,
				coalesce(r.RelationType, "UNKNOWN") AS rt
			WITH a,b,r,
				CASE rt
				WHEN "RET" THEN "RET"
				WHEN "SO"  THEN "SO"
				WHEN "NV"  THEN "NV"
				WHEN "ARG" THEN "ARG"
				WHEN "DEP" THEN "DEP"
				WHEN "TAINT" THEN "TAINT"
				WHEN "USER_TAINT" THEN "USER_TAINT"
				ELSE "UNKNOWN"
				END AS t
			CALL apoc.create.relationship(a, t, properties(r), b) YIELD rel
			RETURN count(rel) AS created
			"""
		
		session.run(change_graph)

		delete_old_rels = """
			MATCH ()-[r:PDG]->()
			DELETE r
		"""

		session.run(delete_old_rels)

		get_call_graph = """
				MATCH 
					(func:VariableDeclarator)
						-[ref_edge:REF]
							->(call:PDG_CALL)
								-[:CG]
									->(called_func:VariableDeclarator),
					(func)
						-[:AST]
							->(callee)
				WHERE
					ref_edge.RelationType = "call" AND (callee.Type="FunctionExpression" OR callee.Type="ArrowFunctionExpression")
					RETURN DISTINCT func, COLLECT({call: call, called_func: called_func}) AS calls
		"""

		# Check the taint propagation according to the call graph
		cg = {}
		results = session.run(get_call_graph)

		for record in results:
			func = record["func"]["Id"]
			cg[func] = set(map(lambda x: (x["call"]["Id"], x["called_func"]["Id"]), record["calls"]))


		get_outer_funcs = """
			MATCH 
					(func:VariableDeclarator)
						-[ref_edge:REF]
							->(call:PDG_CALL)
								-[:CG]
									->(called_func:VariableDeclarator),
					(func)
						-[:AST]
							->(callee)
				WHERE
					ref_edge.RelationType = "call" AND (callee.Type="FunctionExpression" OR callee.Type="ArrowFunctionExpression")

			OPTIONAL MATCH
				(outer_func:VariableDeclarator)-[init_edge:AST]->(:FunctionExpression)-[block_edge:AST]->(outer_block:BlockStatement)
					WHERE
						init_edge.RelationType = "init"
						AND block_edge.RelationType = "block"

				MATCH
					(outer_block)-[edge:AST]->(func)
					WHERE
						edge.RelationType = "stmt"

			RETURN DISTINCT func, outer_func
		"""

		outer_results = session.run(get_outer_funcs)

		for record in outer_results:
			func = record["func"]["Id"]
			outer_func = record["outer_func"]

			if outer_func is None:
				continue

			outer_func_id = outer_func["Id"]

			if func not in cg:
				continue

			self.outer_funcs[func] = outer_func_id

		visited = set()
		for start in cg.keys():
			if start not in visited:
				process_call_graph(session, cg, start, visited)

		verify_source_granularity = """
		MATCH 
			(a)-[r:USER_TAINT]->(b)
		RETURN r;
		"""

		verify_user_taint = session.run(verify_source_granularity)

		if verify_user_taint.peek():
			mark_exported_params = """
				MATCH
					(:TAINT_SOURCE)
						-[taint:USER_TAINT]
							->(param:PDG_OBJECT)
		
				SET param.isExported = true	
			"""
		else:
			mark_exported_params = """
				MATCH
					(:TAINT_SOURCE)
						-[taint:TAINT]
							->(param:PDG_OBJECT)
		
				SET param.isExported = true	
			"""

		session.run(mark_exported_params)

		self.transpose_cg(cg)

	def transpose_cg(self, cg):
		for caller in cg:
			for callee in cg[caller]:
				callee_name = callee[1]

				if callee_name not in self.cgt:
					self.cgt[callee_name] = set()

				self.cgt[callee_name].add(caller)

	def confirm_vulnerability(self, session, funcId, startParam, visited=set()):

		def get_calls_to_param(session, func, param):
			# gets all the calls that appear in the function (func) to the specified parameter (param)
			get_calls_to_param_query = f"""
				MATCH
					(func:VariableDeclarator)
						-[ref_edge:REF]
							->(call:PDG_CALL)
								-[:CG]
									->(called_func:VariableDeclarator),
					(obj:PDG_OBJECT)
						-[arg_edge]
							->(call)
				WHERE
					ref_edge.RelationType = "call" AND
					func.Id = \"{func}\" AND
					arg_edge.IdentifierName = \"{param}\"

				WITH call.Id AS callId, collect(DISTINCT obj.Id)[0] AS argId
				RETURN apoc.map.fromPairs(collect([callId, argId])) AS call_to_argId
			"""

			return session.run(get_calls_to_param_query).single()["call_to_argId"]

		def get_calls_argument(session, call_id, arg_id, func):

			query = f"""
				MATCH (func:VariableDeclarator)-[ref_edge:REF]->(param:PDG_OBJECT) WHERE func.Id = \"{func}\" 
				
				CALL apoc.path.expandConfig(param, {{ relationshipFilter: "RET>|DEP>|NV>|ARG>|SO", labelFilter: "+PDG_OBJECT|>PDG_CALL", 
				minLevel: 1, 
				maxLevel: 15, 
				uniqueness: "NODE_PATH", 
				bfs: true, 
				filterStartNode: false }}) 
				
				YIELD path WITH param, 
				last(nodes(path)) AS call, 
				relationships(path) AS rels, 
				nodes(path) AS ns 
				
				WHERE call:PDG_CALL AND 
				call.Id = \"{call_id}\" AND 
				size(ns) >= 2 AND 
				ns[-2]:PDG_OBJECT AND 
				ns[-2].Id = \"{arg_id}\" AND 
				ALL(r IN rels[..-1] WHERE type(r) <> "ARG" OR r.valid = true) 
				
				RETURN collect(DISTINCT param) AS params
			"""			

			return session.run(query).single()["params"]

		if startParam["isExported"]:
			return True, startParam["Id"]

		if startParam["IdentifierName"] in self.paramInfo:  # simply use the cached information
			return self.paramInfo[startParam["IdentifierName"]]

		visited.add(startParam["IdentifierName"])

		if funcId in self.cgt:
			for caller in self.cgt[funcId]:
				outer_func = self.outer_funcs.get(caller, None)
				results  = get_calls_to_param(session, caller, startParam["IdentifierName"])

				for call_id, arg_id in results.items():
					
					params = []
					if outer_func is not None:
						params = get_calls_argument(session, call_id, arg_id, outer_func)

						for param in params:
							if not param["IdentifierName"] in visited:
								result, paramId = self.confirm_vulnerability(session, outer_func, param)
								self.paramInfo[param["IdentifierName"]] = (result, paramId)
								if result:
									return True, paramId
					params += get_calls_argument(session, call_id, arg_id, caller)

					for param in params:
						if not param["IdentifierName"] in visited:
							result, paramId = self.confirm_vulnerability(session, caller, param)
							self.paramInfo[param["IdentifierName"]] = (result, paramId)
							if result:
								return True, paramId

		return False, None

	# Timer related functions
	def start_timer(self):
		self.start_time = time.time()

	def time_detection(self, type):
		detection_time = (time.time() - self.start_time) * 1000  # to ms
		print(f'{type}_detection: {detection_time}', file=open(self.time_output_file, 'a'))
		self.start_timer()

	def time_reconstruction(self, type):
		reconstruction_time = (time.time() - self.start_time) * 1000  # to ms
		print(f'{type}_reconstruction: {reconstruction_time}', file=open(self.time_output_file, 'a'))

