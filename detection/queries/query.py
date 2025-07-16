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

				OPTIONAL MATCH 
						(param)
						-[edges:PDG*1..]
							->(return:PDG_RETURN)
						WHERE ALL(
						edge in edges WHERE
						NOT edge.RelationType = "ARG" OR
						edge.valid = true
					)	

				OPTIONAL MATCH
					(param)-[edge:PDG]->(prop:PDG_OBJECT)
					<-[edges1:PDG*1..]-(obj:PDG_OBJECT)
					-[edge2:PDG]->(indirectReturn:PDG_RETURN)

					WHERE
						edge.RelationType = "DEP" AND
						ALL(
						edge1 in edges1 WHERE
						edge1.RelationType in ["SO","NV"] ) AND
						edge2.RelationType = "DEP"

				WITH 
					param,
					coalesce(return, indirectReturn) AS ret,
					obj

				WHERE 
					ret IS NOT NULL

				MATCH
					(obj1:PDG_OBJECT)
						-[arg_edge:PDG]
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

		visited = set()
		for start in cg.keys():
			if start not in visited:
				process_call_graph(session, cg, start, visited)

		mark_exported_params = """
			MATCH
				(:TAINT_SOURCE)
					-[taint:PDG]
						->(param:PDG_OBJECT)
			WHERE
				taint.RelationType = 'TAINT'
	
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
						-[arg_edge:PDG]
							->(call)
				WHERE
					ref_edge.RelationType = "call" AND
					func.Id = \"{func}\" AND
					arg_edge.IdentifierName = \"{param}\"

				RETURN collect(DISTINCT call.Id) as calls
			"""

			return session.run(get_calls_to_param_query).single()["calls"]

		def get_calls_argument(session, calls, func):
			callIds = "[" + ",".join(map(lambda x: f"\"{x}\"", calls)) + "]"
			# gets the parameters that influence the call
			query = f"""
				MATCH
					(func:VariableDeclarator)
						-[ref_edge:REF]
							->(param:PDG_OBJECT)
								-[edges:PDG*1..]
									->(call:PDG_CALL)
				WHERE
					ALL(
							edge in edges[..-1] WHERE
							NOT edge.RelationType = "ARG" OR
							edge.valid = true
					) AND
					call.Id IN {callIds} AND
					func.Id = \"{func}\"

				RETURN collect(DISTINCT param) as params
			"""

			return session.run(query).single()["params"]

		if startParam["isExported"]:
			return True

		if startParam["IdentifierName"] in self.paramInfo:  # simply use the cached information
			return self.paramInfo[startParam["IdentifierName"]]

		visited.add(startParam["IdentifierName"])

		if funcId in self.cgt:
			for caller in self.cgt[funcId]:
				calls = get_calls_to_param(session, caller, startParam["IdentifierName"])
				params = get_calls_argument(session, calls, caller)

				for param in params:
					if not param["IdentifierName"] in visited:
						result = self.confirm_vulnerability(session, caller, param)
						self.paramInfo[param["IdentifierName"]] = result
						if result:
							return True

		return False

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

