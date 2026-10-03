"""Check geometric bindings against the actual computation, not just shapes."""
from copy import deepcopy
import unittest
from playground_v2.experience import _check_views, evaluate_experiment, default_inputs
from playground_v2.validation import ValidationError


def geometry():
    variables = []
    for key, value in [('q', [[1, 0]]), ('k', [[1, 0], [0, 1]]), ('v', [[1, 2], [-1, 0]])]:
        variables.append(dict(id=key, label=key, type='matrix', default=value,
                              domain=dict(min=-2,max=2,step=.1,rows=len(value),columns=2),unit='',explanation=key))
    bindings=dict(query_input='q',key_input='k',value_input='v',scores_output='scores',weights_output='weights',result_output='result')
    expressions=[('scores',['matmul','$input.q',['transpose','$input.k']]),
                 ('weights',['array',['softmax',['divide',['at','$output.scores',0],['sqrt',2]]]]),
                 ('result',['matmul','$output.weights','$input.v'])]
    return dict(id='geometry',variables=variables,computation=dict(
        outputs=[dict(id=i,label=i,unit='') for i,_ in expressions],
        steps=[dict(id='step_'+i,label=i,explanation=i,output_ids=[i],expressions={i:expr}) for i,expr in expressions]),
        views=[dict(id=kind,kind=kind,title=kind,output_ids=['scores','weights','result'],labels=[],bindings=deepcopy(bindings)) for kind in ['vector_compare','weight_distribution','weighted_blend','contribution_flow']])


class DiagramBindingTests(unittest.TestCase):
    def test_valid_geometry_and_degenerate_inputs(self):
        exp=geometry()
        for q,k,v in [([[1,0]],[[1,0],[0,1]],[[1,2],[-1,0]]),
                      ([[0,0]],[[0,0],[0,0]],[[1,1],[1,1]]),
                      ([[-2,2]],[[2,-2],[-2,2]],[[-2,0],[2,0]])]:
            inputs=dict(q=q,k=k,v=v)
            _check_views(exp,evaluate_experiment(exp,inputs),inputs=inputs)

    def test_single_query_vector_bindings_are_checked_as_one_row(self):
        exp=geometry(); result=evaluate_experiment(exp,default_inputs(exp))
        inputs=default_inputs(exp); inputs['q']=inputs['q'][0]
        for key in ('scores','weights','result'): result['outputs'][key]=result['outputs'][key][0]
        _check_views(exp,result,inputs=inputs)

    def test_refuses_false_weighted_geometry_even_when_shapes_match(self):
        exp=geometry(); result=evaluate_experiment(exp,default_inputs(exp))
        result['outputs']['result'][0][0]+=1
        with self.assertRaisesRegex(ValidationError,'weighted values'):
            _check_views(exp,result)

    def test_refuses_scaled_scores_labeled_as_raw(self):
        exp=geometry(); result=evaluate_experiment(exp,default_inputs(exp))
        result['outputs']['scores'][0][0]/=2
        with self.assertRaisesRegex(ValidationError,'raw score'):
            _check_views(exp,result)

    def test_refuses_nonprobability_weights(self):
        exp=geometry(); result=evaluate_experiment(exp,default_inputs(exp))
        result['outputs']['weights'][0]=[-1,2]
        with self.assertRaisesRegex(ValidationError,'nonnegative'):
            _check_views(exp,result)

    def test_rejects_unknown_input_binding(self):
        exp=geometry();exp['views'][0]['bindings']['query_input']='missing'
        with self.assertRaises(ValidationError):
            _check_views(exp,evaluate_experiment(exp,default_inputs(exp)))


if __name__=='__main__': unittest.main()
