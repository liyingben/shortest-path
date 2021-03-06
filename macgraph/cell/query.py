
import tensorflow as tf

from ..attention import *
from ..util import *
from .types import *

def generate_token_index_query(context:CellContext, name:str):
	with tf.name_scope(name):
		with tf.variable_scope(name):

			taps = {}

			master_signal = context.in_iter_id

			tokens = pad_to_table_len(context.embedded_question, seq_len=context.args["max_seq_len"], name=name)
			token_index_signal, query = attention_by_index(tokens, None)
			
			output = token_index_signal
			taps["token_index_attn"] = tf.expand_dims(query, 2)

			return output, taps



def generate_query(context:CellContext, name):
	with tf.name_scope(name):

		taps = {}
		sources = []

		def add_taps(prefix, extra_taps):
			for k, v in extra_taps.items():
				taps[prefix + "_" + k] = v

		# --------------------------------------------------------------------------
		# Produce all the difference sources of addressing query
		# --------------------------------------------------------------------------

		ms = [context.in_iter_id]

		master_signal = tf.concat(ms, -1)

		# Content address the question tokens
		token_query = tf.layers.dense(master_signal, context.args["embed_width"])
		token_signal, _, x_taps = attention(context.in_question_tokens, token_query)
		sources.append(token_signal)
		add_taps("token_content", x_taps)

		# Index address the question tokens
		padding = [[0,0], [0, tf.maximum(0,context.args["max_seq_len"] - tf.shape(context.in_question_tokens)[1])], [0,0]] # batch, seq_len, token
		in_question_tokens_padded = tf.pad(context.in_question_tokens, padding)
		in_question_tokens_padded.set_shape([None, context.args["max_seq_len"], None])

		token_index_signal, query = attention_by_index(in_question_tokens_padded, master_signal)
		sources.append(token_index_signal)
		taps["token_index_attn"] = tf.expand_dims(query, 2)

		if context.args["use_read_previous_outputs"]:
			# Use the previous output of the network
			prev_output_query = tf.layers.dense(master_signal, context.args["output_width"])
			in_prev_outputs_padded = tf.pad(context.in_prev_outputs, [[0,0],[0, context.args["max_decode_iterations"] - tf.shape(context.in_prev_outputs)[1]],[0,0]])
			prev_output_signal, _, x_taps = attention(in_prev_outputs_padded, prev_output_query)
			sources.append(prev_output_signal)
			add_taps("prev_output", x_taps)

		# --------------------------------------------------------------------------
		# Choose a query source
		# --------------------------------------------------------------------------

		query_signal, q_tap = attention_by_index(tf.stack(sources, 1), master_signal)
		taps["switch_attn"] = q_tap

		return query_signal, taps
