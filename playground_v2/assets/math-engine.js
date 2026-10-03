/* Trusted deterministic numerical interpreter. Expressions are data only. */
function createDeclarativeModel(spec) {
  'use strict';
  const MAX_DEPTH=24, MAX_NODES=4096, MAX_ARRAY=200, MAX_ELEMENTS=4096;
  const variables=spec.variables, steps=spec.steps, constraints=spec.constraints||[];
  const copy=value=>JSON.parse(JSON.stringify(value));
  const fail=message=>{throw new Error(message);};
  const number=value=>typeof value==='number'&&Number.isFinite(value);
  function inspect(value,depth=0,counter={count:0}) {
    if(depth>MAX_DEPTH||++counter.count>MAX_ELEMENTS)fail('Numerical value exceeds supported size.');
    if(Array.isArray(value)){if(value.length>MAX_ARRAY)fail('Array exceeds supported size.');value.forEach(x=>inspect(x,depth+1,counter));}
    else if(!number(value))fail('Expected a finite numerical value.');
    return value;
  }
  function pathValue(root,path) {
    const parts=path.replace(/\[(\d+)\]/g,'.$1').split('.');let value=root;
    for(const part of parts){if(!part||['constructor','prototype','__proto__'].includes(part)||value==null||!Object.prototype.hasOwnProperty.call(value,part))fail('Unknown numerical reference: '+path);value=value[part];}
    return copy(value);
  }
  function unary(value,op){if(Array.isArray(value))return value.map(x=>unary(x,op));if(!number(value))fail('Operation needs a numerical value.');return op(value);}
  function binary(left,right,op){
    if(Array.isArray(left)&&Array.isArray(right)){if(left.length!==right.length||left.some((x,i)=>Array.isArray(x)!==Array.isArray(right[i])))fail('Elementwise dimensions do not match.');return left.map((x,i)=>binary(x,right[i],op));}
    if(Array.isArray(left))return left.map(x=>binary(x,right,op));
    if(Array.isArray(right))return right.map(x=>binary(left,x,op));
    if(!number(left)||!number(right))fail('Operation needs numerical operands.');return op(left,right);
  }
  function flatten(value){inspect(value);return Array.isArray(value)?value.flat(MAX_DEPTH):[value];}
  function vector(value){if(!Array.isArray(value)||!value.length||!value.every(number))fail('Operation needs a nonempty numerical vector.');return value;}
  function matrix(value){if(!Array.isArray(value)||!value.length||!Array.isArray(value[0])||!value[0].length)fail('Operation needs a nonempty matrix.');const width=value[0].length;if(!value.every(row=>Array.isArray(row)&&row.length===width&&row.every(number)))fail('Matrix rows must have equal numerical lengths.');if(value.length*width>MAX_ELEMENTS)fail('Matrix is too large.');return value;}
  function dot(left,right){vector(left);vector(right);if(left.length!==right.length)fail('Dot product dimensions do not match.');return left.reduce((sum,x,i)=>sum+x*right[i],0);}
  function transpose(value){matrix(value);return value[0].map((_,col)=>value.map(row=>row[col]));}
  function resolve(expression,inputs,outputs,depth,budget){
    if(depth>MAX_DEPTH||++budget.count>MAX_NODES)fail('Expression exceeds supported complexity.');
    if(typeof expression==='string'){
      if(expression.startsWith('$input.'))return pathValue(inputs,expression.slice(7));
      if(expression.startsWith('$output.'))return pathValue(outputs,expression.slice(8));
      return expression;
    }
    if(!Array.isArray(expression))return expression;
    if(!expression.length||typeof expression[0]!=='string')return copy(expression);
    const op=expression[0],args=expression.slice(1),run=x=>resolve(x,inputs,outputs,depth+1,budget);
    if(op==='literal')return copy(args[0]);
    if(op==='if'){const condition=run(args[0]);if(typeof condition!=='boolean')fail('Conditional needs a boolean condition.');return run(condition?args[1]:args[2]);}
    const values=args.map(run),a=values[0],b=values[1];
    switch(op){
      case 'add':return binary(a,b,(x,y)=>x+y);
      case 'subtract':return binary(a,b,(x,y)=>x-y);
      case 'multiply':return binary(a,b,(x,y)=>x*y);
      case 'divide':return binary(a,b,(x,y)=>{if(y===0)fail('Cannot divide by zero.');return x/y;});
      case 'power':return binary(a,b,(x,y)=>Math.pow(x,y));
      case 'negate':return unary(a,x=>-x);
      case 'abs':return unary(a,Math.abs);
      case 'sqrt':return unary(a,x=>{if(x<0)fail('Square root needs a nonnegative value.');return Math.sqrt(x);});
      case 'exp':return unary(a,Math.exp);
      case 'log':return unary(a,x=>{if(x<=0)fail('Logarithm needs a positive value.');return Math.log(x);});
      case 'log2':return unary(a,x=>{if(x<=0)fail('Logarithm needs a positive value.');return Math.log2(x);});
      case 'xlogx':{const base=values.length>1?b:Math.E;if(!number(base)||base<=0||base===1)fail('Logarithm base must be positive and different from one.');return unary(a,x=>{if(x<0)fail('x log x needs nonnegative values.');return x===0?0:x*Math.log(x)/Math.log(base);});}
      case 'sum':return flatten(a).reduce((sum,x)=>sum+x,0);
      case 'mean':{const flat=flatten(a);if(!flat.length)fail('Mean needs at least one value.');return flat.reduce((sum,x)=>sum+x,0)/flat.length;}
      case 'min':{const flat=flatten(a);if(!flat.length)fail('Minimum needs at least one value.');return Math.min(...flat);}
      case 'max':{const flat=flatten(a);if(!flat.length)fail('Maximum needs at least one value.');return Math.max(...flat);}
      case 'dot':return dot(a,b);
      case 'matvec':{matrix(a);vector(b);return a.map(row=>dot(row,b));}
      case 'matmul':{matrix(a);matrix(b);if(a[0].length!==b.length)fail('Matrix multiplication dimensions do not match.');if(a.length*b[0].length>MAX_ELEMENTS)fail('Matrix result exceeds supported size.');const columns=transpose(b);return a.map(row=>columns.map(column=>dot(row,column)));}
      case 'transpose':return transpose(a);
      case 'softmax':{vector(a);const maximum=Math.max(...a),exponents=a.map(x=>Math.exp(x-maximum)),total=exponents.reduce((sum,x)=>sum+x,0);return exponents.map(x=>x/total);}
      case 'normalize':{vector(a);if(a.some(x=>x<0))fail('Normalization needs nonnegative values.');const maximum=Math.max(...a);if(maximum<=0)fail('Normalization needs a positive sum.');const scaled=a.map(x=>x/maximum),total=scaled.reduce((sum,x)=>sum+x,0);return scaled.map(x=>x/total);}
      case 'array':return values;
      case 'at':{if(!Array.isArray(a)||!Number.isInteger(b)||b<0||b>=a.length)fail('Array index is out of range.');return copy(a[b]);}
      case 'concat':{if(!values.every(Array.isArray))fail('Concatenation needs arrays.');const result=values.flat(1);if(result.length>MAX_ARRAY)fail('Concatenated array is too large.');return result;}
      case 'slice':{const end=values.length>2?values[2]:a?.length;if(!Array.isArray(a)||!Number.isInteger(b)||!Number.isInteger(end)||b<0||end<b||end>a.length)fail('Slice bounds are invalid.');return a.slice(b,end);}
      case 'length':{if(!Array.isArray(a))fail('Length needs an array.');return a.length;}
      case 'eq':{if(Array.isArray(a)||Array.isArray(b))fail('Comparison needs scalar values.');return a===b;}
      case 'lt':{if(!number(a)||!number(b))fail('Comparison needs numerical values.');return a<b;}
      case 'gt':{if(!number(a)||!number(b))fail('Comparison needs numerical values.');return a>b;}
      default:fail('Unsupported numerical operation: '+op);
    }
  }
  function predicateValue(operand,inputs){if(operand.kind==='constant')return operand.value;if(operand.kind==='input')return pathValue(inputs,operand.path.replace(/^inputs\./,''));fail('Input constraints can reference inputs only.');}
  function approximately(a,b,p){if(Array.isArray(a)||Array.isArray(b))return Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((v,i)=>approximately(v,b[i],p));return number(a)&&number(b)&&Math.abs(a-b)<=(p.absolute_tolerance??1e-6)+(p.relative_tolerance??1e-5)*Math.abs(b);}
  function constraintPass(p,inputs,depth=0){
    if(depth>12)fail('Constraint exceeds supported complexity.');
    if(p.op==='all')return p.children.length>0&&p.children.every(c=>constraintPass(c,inputs,depth+1));
    if(p.op==='any')return p.children.some(c=>constraintPass(c,inputs,depth+1));
    const a=predicateValue(p.operands[0],inputs),b=p.operands[1]?predicateValue(p.operands[1],inputs):null;
    if(p.op==='eq'&&!number(a)&&!Array.isArray(a))return a===b;
    if(['eq','approx','agreement'].includes(p.op))return approximately(a,b,p);
    if(p.op==='range')return number(a)&&a>=p.min&&a<=p.max;
    if(p.op==='gt')return number(a)&&number(b)&&a>b+(p.margin||0);
    if(p.op==='lt')return number(a)&&number(b)&&a<b-(p.margin||0);
    if(p.op==='normalized_sum')return Array.isArray(a)&&a.every(x=>number(x)&&x>=0)&&approximately(a.reduce((sum,x)=>sum+x,0),p.expected??1,p);
    if(p.op==='argmax'){vector(a);const maximum=Math.max(...a),indices=a.map((v,i)=>Math.abs(v-maximum)<=(p.absolute_tolerance??1e-6)?i:-1).filter(i=>i>=0),accepted=p.accepted_indices||[];if(p.tie_policy==='first')return accepted.includes(indices[0]);if(p.tie_policy==='any')return indices.some(i=>accepted.includes(i));return indices.length===1&&accepted.includes(indices[0]);}
    fail('Unsupported input constraint.');
  }
  function validateInputs(inputs){
    const errors=[];const error=(path,message)=>errors.push({path,code:'invalid_input',message});
    if(!inputs||typeof inputs!=='object'||Array.isArray(inputs))return {valid:false,errors:[{path:'',code:'invalid_input',message:'Provide an input object.'}]};
    const known=new Set(variables.map(v=>v.id));Object.keys(inputs).forEach(id=>{if(!known.has(id))error(id,'Unknown input.');});
    variables.forEach(variable=>{
      const value=inputs[variable.id],domain=variable.domain||{},path=variable.id;
      const scalar=(x,p)=>{if(!number(x))error(p,'Enter a finite number.');else if(domain.min!=null&&x<domain.min)error(p,'Value is below the allowed minimum.');else if(domain.max!=null&&x>domain.max)error(p,'Value is above the allowed maximum.');};
      if(variable.type==='boolean'){if(typeof value!=='boolean')error(path,'Choose on or off.');}
      else if(variable.type==='enum'){if(typeof value!=='string'||!domain.values.includes(value))error(path,'Choose a declared option.');}
      else if(variable.type==='number'||variable.type==='integer'){scalar(value,path);if(variable.type==='integer'&&number(value)&&!Number.isInteger(value))error(path,'Enter a whole number.');}
      else if(variable.type==='vector'){if(!Array.isArray(value)||value.length!==domain.length)error(path,'Vector length must be '+domain.length+'.');else value.forEach((x,i)=>scalar(x,path+'.'+i));}
      else if(variable.type==='matrix'){if(!Array.isArray(value)||value.length!==domain.rows||!value.every(row=>Array.isArray(row)&&row.length===domain.columns))error(path,'Matrix shape must be '+domain.rows+' × '+domain.columns+'.');else value.forEach((row,i)=>row.forEach((x,j)=>scalar(x,path+'.'+i+'.'+j)));}
      else error(path,'Unsupported input type.');
    });
    if(!errors.length)constraints.forEach((predicate,index)=>{try{const passed=typeof PlaygroundCore!=='undefined'?PlaygroundCore.evaluatePredicate(predicate,{inputs,outputs:{}}):constraintPass(predicate,inputs);if(!passed)error(predicate.operands?.find(o=>o.kind==='input')?.path?.replace(/^inputs\./,'')||'', 'Input constraint '+(index+1)+' is not satisfied.');}catch(e){error('',e.message);}});
    return {valid:errors.length===0,errors};
  }
  function compute(inputs){
    const validation=validateInputs(inputs);if(!validation.valid)fail(validation.errors.map(e=>e.message).join(' '));
    const outputs={},results=[],budget={count:0};
    for(const step of steps){const values={};for(const [id,expression] of Object.entries(step.expressions)){try{const value=resolve(expression,inputs,outputs,0,budget);inspect(value);outputs[id]=copy(value);values[id]=copy(value);}catch(error){error.step_id=step.id;error.output_id=id;error.completed_outputs=copy(outputs);throw error;}}results.push({id:step.id,values});}
    return {outputs,steps:results};
  }
  return {validateInputs,compute};
}
