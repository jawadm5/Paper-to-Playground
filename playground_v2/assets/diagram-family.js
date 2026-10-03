/* Scientific displays bind only to the trusted engine's inputs and outputs. */
window.ResearchDiagrams = (() => {
  const kinds = new Set(['vector_compare','weight_distribution','weighted_blend','contribution_flow','process']);
  const el = (tag, attrs={}, text) => { const n=document.createElement(tag); Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v)); if(text!==undefined)n.textContent=text; return n; };
  const sv = (tag,attrs={},text) => {const n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;return n;};
  const fmt = x => Number(x.toPrecision(5)).toString();
  function create(view, exp, changed) {
    const node=el('section',{class:'view science-view','data-view':view.id,'data-kind':view.kind});
    node.append(el('h3',{},view.title)); if(view.explanation)node.append(el('p',{},view.explanation));
    const toolbar=el('div',{class:'diagram-tools'}), body=el('div',{class:'diagram-body'}), values=el('div',{class:'diagram-values'});
    node.append(toolbar,body,values); let current, selected=0, step=0;
    const b=view.bindings||{}, query=exp.variables.find(x=>x.id===b.query_input);
    let rowSelect, rotate;
    if(query && query.domain.rows>1){const label=el('label',{},'Selected query ');rowSelect=el('select',{'aria-label':'Selected query'});for(let i=0;i<query.domain.rows;i++)rowSelect.append(el('option',{value:i},'Query '+(i+1)));rowSelect.onchange=()=>{selected=Number(rowSelect.value);changed.select(selected);};label.append(rowSelect);toolbar.append(label);}
    if(view.kind==='vector_compare') {
      const label=el('label',{},'Query direction ');rotate=el('input',{type:'range',min:-180,max:180,step:1,'aria-label':'Query direction'});label.append(rotate);toolbar.append(label);
      rotate.oninput=()=>{const raw=current.inputs[b.query_input],q=Array.isArray(raw[0])?raw.map(r=>r.slice()):[raw.slice()],radius=Math.hypot(...q[selected]),angle=Number(rotate.value)*Math.PI/180; const next=[radius*Math.cos(angle),radius*Math.sin(angle)];if(next.every(x=>x>=query.domain.min-1e-10&&x<=query.domain.max+1e-10)){q[selected]=next;changed.input(b.query_input,Array.isArray(raw[0])?q:q[0]);}};
    }
    const processButtons=[];let previousStep,nextStep;
    if(view.kind==='process') {
      const steps=el('div',{class:'process-track',role:'group','aria-label':'Calculation stages'});
      exp.computation.steps.forEach((s,i)=>{const n=el('button',{type:'button','data-process-step':s.id},(i+1)+'. '+s.label);n.onclick=()=>{step=i;draw();};processButtons.push(n);steps.append(n);}); toolbar.append(steps);previousStep=el('button',{type:'button'},'Previous step');nextStep=el('button',{type:'button'},'Next step');previousStep.onclick=()=>{step=Math.max(0,step-1);draw();};nextStep.onclick=()=>{step=Math.min(exp.computation.steps.length-1,step+1);draw();};toolbar.append(previousStep,nextStep);
    }
    function plot(title,extent){
      const svg=sv('svg',{viewBox:'0 0 400 330',role:'img','aria-label':title});
      const scale=125/Math.max(extent,1e-9), xy=p=>[200+p[0]*scale,165-p[1]*scale];
      [[[-extent,0],[extent,0]],[[0,-extent],[0,extent]]].forEach(([a,b])=>{const p=xy(a),q=xy(b);svg.append(sv('line',{x1:p[0],y1:p[1],x2:q[0],y2:q[1],stroke:'var(--line)'}));});
      svg.append(sv('text',{x:345,y:184},'x'),sv('text',{x:210,y:30},'y'),sv('text',{x:20,y:320},'Equal axes · −'+fmt(extent)+' to '+fmt(extent)));
      return {svg,xy};
    }
    function draw(){
      if(!current)return; const {inputs,run,presentation}=current; selected=presentation.selectedQuery||0; if(rowSelect)rowSelect.value=selected;
      body.replaceChildren();values.replaceChildren();
      if(view.kind==='process') {
        const s=exp.computation.steps[step];previousStep.disabled=step===0;nextStep.disabled=step===exp.computation.steps.length-1;processButtons.forEach((n,i)=>n.setAttribute('aria-pressed',String(i===step)));
        body.append(el('p',{},s.explanation));
        const refs=[...new Set(JSON.stringify(s.expressions).match(/\$output\.[a-z][a-z0-9_]*/g)||[])].map(x=>x.slice(8));
        body.append(el('p',{class:'muted small'},'Uses: '+(refs.length?refs.map(id=>exp.computation.outputs.find(o=>o.id===id)?.label||id).join(', '):'experiment inputs')));
        s.output_ids.forEach(id=>values.append(el('p',{},(exp.computation.outputs.find(o=>o.id===id)?.label||id)+' = '+JSON.stringify(run.outputs[id])))); return;
      }
      const rows=x=>Array.isArray(x[0])?x:[x];const q=rows(inputs[b.query_input]),k=inputs[b.key_input],v=inputs[b.value_input],scores=rows(run.outputs[b.scores_output])[selected],weights=rows(run.outputs[b.weights_output])[selected],out=rows(run.outputs[b.result_output])[selected];
      const names=k.map((_,i)=>view.labels[i]||'Key '+(i+1));
      if(rotate){const radius=Math.hypot(...q[selected]),limit=Math.min(query.domain.max,-query.domain.min);rotate.disabled=radius<1e-10||radius>limit+1e-10;rotate.value=Math.atan2(q[selected][1],q[selected][0])*180/Math.PI;rotate.title=radius<1e-10?'Zero vector has no direction':radius>limit?'Reduce query length to rotate within all component bounds':'Rotate while preserving length';}
      if(view.kind==='weight_distribution') {
        weights.forEach((w,i)=>{const row=el('div',{class:'weight-row'}),track=el('div',{class:'weight-track'}),bar=el('div',{class:'weight-fill'});bar.style.width=(100*w)+'%';track.append(bar);row.append(el('span',{},names[i]),el('span',{},'score '+fmt(scores[i])),track,el('strong',{},(100*w).toFixed(1)+'%'));body.append(row);});
        values.append(el('p',{class:'small muted'},'Common probability scale: 0–100%. Sum = '+fmt(weights.reduce((a,b)=>a+b,0))));
      } else if(view.kind==='vector_compare') {
        const vars=[query,exp.variables.find(x=>x.id===b.key_input)],extent=Math.max(...vars.flatMap(x=>[Math.abs(x.domain.min),Math.abs(x.domain.max)]))*1.12;const {svg,xy}=plot(view.title,extent); const max=Math.max(...scores);
        const arrow=(p,name,color,index)=>{const [x,y]=xy(p),dx=x-200,dy=y-165,len=Math.hypot(dx,dy);svg.append(sv('line',{x1:200,y1:165,x2:x,y2:y,stroke:color,'stroke-width':3}));if(len>1){const ux=dx/len,uy=dy/len;svg.append(sv('path',{d:`M${x} ${y}L${x-9*ux+4*uy} ${y-9*uy-4*ux}L${x-9*ux-4*uy} ${y-9*uy+4*ux}Z`,fill:color}));}svg.append(sv('text',{x:Math.max(12,Math.min(365,x+8)),y:Math.max(18,Math.min(298,y-9-index*3)),fill:color},name));};
        const labels=new Map();const collect=(p,name)=>{const id=p.map(x=>Math.round(x*1e7)).join(',');if(labels.has(id))labels.get(id).names.push(name);else labels.set(id,{point:p,names:[name]});};
        k.forEach((p,i)=>{arrow(p,'','var(--key)',i);collect(p,'k'+(i+1));});arrow(q[selected],'','var(--query)',0);collect(q[selected],'q');
        labels.forEach(({point,names})=>{const [x,y]=xy(point);svg.append(sv('text',{x:Math.max(12,Math.min(325,x+9)),y:Math.max(18,Math.min(295,y-12))},names.join(' / ')));});body.append(svg);
        values.append(el('p',{},'Highest raw score: '+names.filter((_,i)=>Math.abs(scores[i]-max)<1e-9).join(', ')+(scores.filter(x=>Math.abs(x-max)<1e-9).length>1?' (tie)':'')));
        values.append(el('p',{class:'small'},'q = '+JSON.stringify(q[selected])+' · '+k.map((p,i)=>'k'+(i+1)+' = '+JSON.stringify(p)).join(' · ')));
        if(rotate.disabled) values.append(el('p',{class:'small muted'},rotate.title+'. You can still edit the coordinates.'));
      } else if(view.kind==='weighted_blend') {
        const variable=exp.variables.find(x=>x.id===b.value_input),extent=Math.max(Math.abs(variable.domain.min),Math.abs(variable.domain.max))*1.12,{svg,xy}=plot(view.title,extent);
        // Monotone-chain convex hull, including collinear and coincident values.
        const ps=[...new Map(v.map(p=>[p.join(','),p])).values()].sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const cross=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);
        const half=points=>{const h=[];points.forEach(p=>{while(h.length>=2&&cross(h[h.length-2],h[h.length-1],p)<=0)h.pop();h.push(p);});return h;};const hull=ps.length>1?[...half(ps).slice(0,-1),...half(ps.slice().reverse()).slice(0,-1)]:ps;
        svg.append(sv('polygon',{points:hull.map(x=>xy(x).join(',')).join(' '),fill:'var(--soft)',stroke:'var(--value)'}));const o=xy(out);
        v.forEach((p,i)=>{const a=xy(p);svg.append(sv('line',{x1:a[0],y1:a[1],x2:o[0],y2:o[1],stroke:'var(--value)','stroke-width':1+7*weights[i],opacity:.6}),sv('circle',{cx:a[0],cy:a[1],r:5,fill:'var(--value)'}),sv('text',{x:Math.max(12,Math.min(370,a[0]+9)),y:Math.max(18,Math.min(290,a[1]-9-i*3))},'v'+(i+1)));});svg.append(sv('circle',{cx:o[0],cy:o[1],r:7,fill:'var(--accent)'}),sv('text',{x:o[0]+10,y:Math.min(308,o[1]+21),fill:'var(--accent)'},'output'));body.append(svg);
        values.append(el('p',{},'Output = ['+out.map(fmt).join(', ')+']'),el('p',{class:'small'},weights.map((w,i)=>fmt(w)+' × ['+v[i].map(fmt).join(', ')+']').join(' + ')));
      } else if(view.kind==='contribution_flow') {
        const height=Math.max(220,weights.length*62),svg=sv('svg',{viewBox:`0 0 400 ${height}`,role:'img','aria-label':'Weights flowing from each value to the output'});
        weights.forEach((w,i)=>{const y=30+i*(height-60)/Math.max(1,weights.length-1);svg.append(sv('path',{d:`M110 ${y}C205 ${y},210 ${height/2},300 ${height/2}`,fill:'none',stroke:'var(--value)','stroke-width':w===0?1:Math.max(2,w*40),'stroke-dasharray':w===0?'3 3':'none',opacity:.65}),sv('text',{x:8,y:y+4},'v'+(i+1)+' · '+(w*100).toFixed(1)+'%'));});svg.append(sv('circle',{cx:308,cy:height/2,r:7,fill:'var(--accent)'}),sv('text',{x:320,y:height/2+4},'output'));body.append(svg);values.append(el('p',{},'Weighted output: ['+out.map(fmt).join(', ')+']'),el('p',{class:'small muted'},'Ribbon width encodes the mixing weight, not signed value magnitude. Zero weights use a dashed line.'));
      }
    }
    return {element:node,update(inputs,run,baseline,presentation){current={inputs,run,baseline,presentation};draw();}};
  }
  return {kinds,create};
})();
