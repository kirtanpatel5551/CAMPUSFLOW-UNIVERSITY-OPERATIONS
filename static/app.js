const $=q=>document.querySelector(q);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let page='overview', selectedSection=null, cached={};
let toastTimer;
async function api(path,options={}){
  let res;try{res=await fetch(path,{headers:{'Content-Type':'application/json'},...options});}
  catch{throw Error('Cannot connect to the local server.');}
  const data=await res.json();if(!res.ok)throw Error(data.error||'Request failed.');return data;
}
const post=(path,data)=>api(path,{method:'POST',body:JSON.stringify(data)});
function notify(text){$('#toast').textContent=text;$('#toast').classList.remove('hidden');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.add('hidden'),4300);}
function title(label,description,button=''){return `<div class="page-head"><div><div class="eyebrow">CAMPUSFLOW · ACADEMIC OPERATIONS</div><h1>${label}</h1><p>${description}</p></div>${button}</div>`;}
function badge(s){return `<span class="badge ${esc(s)}">${esc(s)}</span>`;}
function sectionName(s){return `${esc(s.code)} · ${esc(s.course_title)} (${esc(s.term)}, ${esc(s.day)} ${esc(s.start_time)})`;}
function sectionOptions(list){return list.map(s=>`<option value="${s.id}">${sectionName(s)}</option>`).join('');}
function studentOptions(list){return list.map(s=>`<option value="${s.id}">${esc(s.student_no)} · ${esc(s.name)}</option>`).join('');}
function openModal(html){$('#modal-content').innerHTML=html;$('#modal-bg').classList.remove('hidden');}
function closeModal(){$('#modal-bg').classList.add('hidden');}
async function refresh(){try{await render(page);}catch(e){notify(e.message);}}
async function show(next){
  page=next;document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n.dataset.page===next));
  $('#breadcrumb').textContent=next[0].toUpperCase()+next.slice(1);window.scrollTo(0,0);await refresh();
}
async function render(view){
  const routes={overview:overview,students:students,courses:courses,sections:sections,
    enrollment:enrollment,attendance:attendance,gradebook:gradebook,
    announcements:announcements,analytics:analytics,audit:audit};
  await routes[view]();
}
async function overview(){
  const d=await api('/api/overview'),c=d.counts;cached.sections=d.sections;
  $('#page-content').innerHTML=title('A clearer view of campus.','Your university, in one connected workspace.')+
    `<div class="notice">Welcome to the demo. Start with the Enrollment module to see schedule conflicts and automatic waitlist promotion.</div>
    <div class="metrics">${[['Students',c.students,'♙'],['Courses',c.courses,'▤'],['Active enrollments',c.enrolled,'⇄'],['Waitlisted',c.waitlisted,'◷']].map(m=>`<div class="metric"><span class="icon">${m[2]}</span><label>${m[0].toUpperCase()}</label><strong>${m[1]}</strong><small>Across ${c.sections} sections</small></div>`).join('')}</div>
    <div class="grid-two"><div class="panel"><div class="panel-heading"><h2>Section capacity</h2><button class="outline" data-page="analytics">View analytics →</button></div><div class="bar-list">
      ${d.sections.slice(0,6).map(s=>`<div><div class="list-row"><strong>${esc(s.code)} · ${esc(s.course_title)}</strong><small>${s.enrolled}/${s.capacity} seats · ${s.waitlisted} waiting</small></div><div class="progress"><span style="width:${s.enrolled/s.capacity*100}%"></span></div></div>`).join('')}</div></div>
      <div class="panel"><div class="panel-heading"><h2>Recent activity</h2><button class="outline" data-page="audit">Audit log →</button></div>
      ${d.recent_activity.map(a=>`<div class="list-row"><div><strong>${esc(a.action)}</strong><small>${esc(a.detail)}</small></div><small>${esc(a.created_at.slice(5,16))}</small></div>`).join('')}</div></div>`;
}
async function students(){
  const d=await api('/api/students');cached.students=d.students;
  $('#page-content').innerHTML=title('Students','Manage the student directory and academic programs.',
    '<button class="primary" data-modal="student">+ Add student</button>')+
    `<div class="panel"><div class="controls"><input id="student-search" placeholder="Search by name, email, or student number…"></div><div class="table-scroll"><table><thead><tr><th>STUDENT</th><th>NUMBER</th><th>PROGRAM</th><th>YEAR</th><th>ACTIVE COURSES</th></tr></thead><tbody id="student-rows"></tbody></table></div></div>`;
  const draw=()=>{$('#student-rows').innerHTML=d.students.filter(s=>(s.name+s.email+s.student_no).toLowerCase().includes($('#student-search').value.toLowerCase())).map(s=>`<tr><td><strong>${esc(s.name)}</strong><small>${esc(s.email)}</small></td><td>${esc(s.student_no)}</td><td>${esc(s.program)}</td><td>Year ${s.year}</td><td>${s.active_courses}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">No students found.</td></tr>';};
  $('#student-search').oninput=draw;draw();
}
async function courses(){
  const d=await api('/api/courses');cached.courses=d.courses;
  $('#page-content').innerHTML=title('Course catalog','Explore academic offerings and add new courses.',
    '<button class="primary" data-modal="course">+ Add course</button>')+
    `<div class="data-grid">${d.courses.map(c=>`<div class="data-card"><span class="code">${esc(c.code)}</span><h3>${esc(c.title)}</h3><p>${esc(c.description)}</p><div class="list-row"><span>${esc(c.department)}</span><strong>${c.credits} credits · ${c.sections} sections</strong></div></div>`).join('')}</div>`;
}
async function sections(){
  const [s,i,c]=await Promise.all([api('/api/sections'),api('/api/instructors'),api('/api/courses')]);
  cached.sections=s.sections;cached.instructors=i.instructors;cached.courses=c.courses;
  $('#page-content').innerHTML=title('Sections & schedules','Plan teaching assignments, rooms, and seat capacity.',
    '<button class="primary" data-modal="section">+ Create section</button>')+
    `<div class="data-grid">${s.sections.map(x=>`<div class="data-card"><span class="code">${esc(x.code)} · ${esc(x.term)}</span><h3>${esc(x.course_title)}</h3><p>♙ ${esc(x.instructor)}<br>◷ ${esc(x.day)} · ${x.start_time}–${x.end_time}<br>⌖ ${esc(x.room)}</p><div class="list-row"><strong>${x.enrolled}/${x.capacity} enrolled</strong><span>${x.waitlisted} waiting</span></div><div class="progress"><span style="width:${x.enrolled/x.capacity*100}%"></span></div></div>`).join('')}</div>`;
}
async function enrollment(){
  const [e,s,st]=await Promise.all([api('/api/enrollments'),api('/api/sections'),api('/api/students')]);
  cached.sections=s.sections;cached.students=st.students;
  $('#page-content').innerHTML=title('Enrollment center','Register students, resolve schedule conflicts, and manage waitlists.')+
    `<div class="panel" style="margin-bottom:18px"><h2>Register a student</h2><p>Full sections automatically place students on a waitlist.</p>
    <form id="enroll-form" class="inline-form"><label>Student<select name="student_id">${studentOptions(st.students)}</select></label><label>Section<select name="section_id">${sectionOptions(s.sections)}</select></label><button class="primary">Register student →</button></form></div>
    <div class="panel"><div class="panel-heading"><h2>Current enrollments</h2><span class="muted small">${e.enrollments.length} active records</span></div><div class="table-scroll"><table><thead><tr><th>STUDENT</th><th>COURSE</th><th>SCHEDULE</th><th>STATUS</th><th></th></tr></thead><tbody>
    ${e.enrollments.map(x=>`<tr><td><strong>${esc(x.student_name)}</strong><small>${esc(x.student_no)}</small></td><td>${esc(x.code)} · ${esc(x.course_title)}</td><td>${esc(x.day)} ${x.start_time}<small>${esc(x.term)}</small></td><td>${badge(x.status)}</td><td><button class="danger" data-drop="${x.id}">Drop</button></td></tr>`).join('')}</tbody></table></div></div>`;
  $('#enroll-form').onsubmit=async ev=>{ev.preventDefault();try{const result=await post('/api/enrollments',Object.fromEntries(new FormData(ev.target)));notify(result.status==='waitlisted'?'Student added to waitlist.':'Student enrolled.');refresh();}catch(error){notify(error.message);}};
}
async function attendance(){
  const s=await api('/api/sections');cached.sections=s.sections;
  if(!selectedSection||!s.sections.some(x=>x.id===selectedSection))selectedSection=s.sections[0]?.id;
  $('#page-content').innerHTML=title('Attendance','Record each student’s attendance by class date.')+
    `<div class="panel"><div class="controls"><select id="attendance-section" class="section-picker">${sectionOptions(s.sections)}</select><input id="attendance-date" type="date"></div><div id="attendance-body"></div></div>`;
  $('#attendance-section').value=selectedSection;$('#attendance-date').value=new Date().toISOString().slice(0,10);
  $('#attendance-section').onchange=ev=>{selectedSection=Number(ev.target.value);drawAttendance();};
  $('#attendance-date').onchange=drawAttendance;await drawAttendance();
}
async function drawAttendance(){
  const d=await api('/api/sections/'+selectedSection+'/attendance');
  const day=$('#attendance-date').value;
  $('#attendance-body').innerHTML=`<div class="table-scroll"><table><thead><tr><th>STUDENT</th><th>DATE</th><th>STATUS</th><th></th></tr></thead><tbody>
    ${d.roster.map(st=>{const mark=d.marks.find(m=>m.student_id===st.id&&m.class_date===day);
      return `<tr><td><strong>${esc(st.name)}</strong><small>${esc(st.student_no)}</small></td><td>${day}</td><td><select id="mark-${st.id}"><option value="present" ${mark?.status==='present'?'selected':''}>Present</option><option value="absent" ${mark?.status==='absent'?'selected':''}>Absent</option><option value="late" ${mark?.status==='late'?'selected':''}>Late</option></select></td><td><button class="outline" data-mark="${st.id}">Save</button></td></tr>`;}).join('')||'<tr><td colspan="4" class="empty">No students enrolled in this section.</td></tr>'}</tbody></table></div>`;
}
async function gradebook(){
  const s=await api('/api/sections');cached.sections=s.sections;
  if(!selectedSection||!s.sections.some(x=>x.id===selectedSection))selectedSection=s.sections[0]?.id;
  $('#page-content').innerHTML=title('Gradebook','Track weighted assessments and student results.')+
    `<div class="controls"><select id="grade-section" class="section-picker">${sectionOptions(s.sections)}</select></div><div id="grade-body"></div>`;
  $('#grade-section').value=selectedSection;
  $('#grade-section').onchange=ev=>{selectedSection=Number(ev.target.value);drawGrades();};
  await drawGrades();
}
async function drawGrades(){
  const d=await api('/api/sections/'+selectedSection+'/gradebook');
  const scores=new Map(d.scores.map(x=>[x.student_id+'-'+x.assessment_id,x.points]));
  $('#grade-body').innerHTML=`<div class="panel" style="margin-bottom:18px"><div class="panel-heading"><h2>Assessments</h2><span class="muted small">Total weight: ${d.total_weight}% / 100%</span></div>
    <div class="list-row">${d.assessments.map(a=>`<span><strong>${esc(a.title)}</strong><small>${a.max_points} points · ${a.weight}% weight</small></span>`).join('')||'<span class="muted">No assessments yet.</span>'}</div>
    <form id="assessment-form" class="inline-form"><label>Assessment<input name="title" required placeholder="e.g. Midterm"></label><label>Max points<input name="max_points" type="number" step="0.1" min="1" required></label><label>Weight %<input name="weight" type="number" step="0.1" min="0.1" max="100" required></label><button class="primary">Add assessment</button></form></div>
    <div class="panel"><div class="panel-heading"><h2>Student scores</h2><span class="muted small">Grade is based on scored assessments</span></div><div class="table-scroll"><table><thead><tr><th>STUDENT</th>${d.assessments.map(a=>`<th>${esc(a.title)} / ${a.max_points}</th>`).join('')}<th>GRADE</th></tr></thead><tbody>
    ${d.roster.map(st=>`<tr><td><strong>${esc(st.name)}</strong></td>${d.assessments.map(a=>`<td><div class="grade-row"><input type="number" min="0" max="${a.max_points}" step="0.1" class="grade-score" id="score-${st.id}-${a.id}" value="${scores.get(st.id+'-'+a.id)??''}" placeholder="—"><button class="outline" data-score="${st.id}:${a.id}">Save</button></div></td>`).join('')}<td><strong>${st.grade===null?'—':st.grade+'%'}</strong></td></tr>`).join('')||'<tr><td class="empty">No enrolled students.</td></tr>'}</tbody></table></div></div>`;
  $('#assessment-form').onsubmit=async ev=>{ev.preventDefault();try{await post('/api/assessments',{...Object.fromEntries(new FormData(ev.target)),section_id:selectedSection});notify('Assessment created.');drawGrades();}catch(error){notify(error.message);}};
}
async function announcements(){
  const [a,s]=await Promise.all([api('/api/announcements'),api('/api/sections')]);cached.sections=s.sections;
  $('#page-content').innerHTML=title('Announcements','Post messages to a course section.',
    '<button class="primary" data-modal="announcement">+ New announcement</button>')+
    `<div class="panel">${a.announcements.map(x=>`<article class="announcement"><span class="code">${esc(x.code)}</span><h3>${esc(x.title)}</h3><p>${esc(x.body)}</p><small>${esc(x.created_at)}</small></article>`).join('')||'<p class="empty">No announcements yet.</p>'}</div>`;
}
async function analytics(){
  const d=await api('/api/analytics'),secs=d.sections;
  const avg=key=>{const vals=secs.map(s=>s[key]).filter(x=>x!==null);return vals.length?(vals.reduce((a,b)=>a+b,0)/vals.length).toFixed(1)+'%':'—';};
  $('#page-content').innerHTML=title('Academic analytics','Measure enrollment demand, attendance, and performance.',
    '<a class="outline" href="/analytics.csv">↓ Export CSV</a>')+
    `<div class="metrics">${[['Average fill rate',avg('fill_rate')],['Attendance rate',avg('attendance_rate')],['Average grade',avg('average_grade')],['Total sections',secs.length]].map(m=>`<div class="metric"><label>${m[0].toUpperCase()}</label><strong>${m[1]}</strong></div>`).join('')}</div>
    <div class="panel"><h2>Section performance</h2><div class="table-scroll"><table><thead><tr><th>SECTION</th><th>TERM</th><th>ENROLLED</th><th>FILL RATE</th><th>ATTENDANCE</th><th>AVERAGE GRADE</th></tr></thead><tbody>
    ${secs.map(s=>`<tr><td><strong>${esc(s.code)} · ${esc(s.course_title)}</strong><small>${esc(s.instructor)}</small></td><td>${esc(s.term)}</td><td>${s.enrolled}/${s.capacity}</td><td><strong>${s.fill_rate}%</strong><div class="progress"><span style="width:${s.fill_rate}%"></span></div></td><td>${s.attendance_rate===null?'—':s.attendance_rate+'%'}</td><td>${s.average_grade===null?'—':s.average_grade+'%'}</td></tr>`).join('')}</tbody></table></div></div>`;
}
async function audit(){
  const d=await api('/api/audit');
  $('#page-content').innerHTML=title('Audit log','Review changes made across the demo workspace.')+
    `<div class="panel">${d.entries.map(a=>`<div class="audit-row"><strong>${esc(a.action)}</strong> · ${esc(a.detail)}<small>${esc(a.created_at)}</small></div>`).join('')}</div>`;
}
function formTemplate(kind){
  if(kind==='student')return ['Add student',`<label>Name<input name="name" required maxlength="120"></label><label>Email<input name="email" type="email" required></label><label>Program<select name="program"><option>Computer Science</option><option>Data Science</option><option>Information Systems</option></select></label><label>Year<input name="year" type="number" min="1" max="6" value="1" required></label>`,'/api/students'];
  if(kind==='course')return ['Add course',`<label>Course code<input name="code" required placeholder="CS580"></label><label>Title<input name="title" required></label><label>Credits<input name="credits" type="number" min="1" max="6" value="3" required></label><label>Department<input name="department" required value="Computer Science"></label><label class="wide">Description<textarea name="description"></textarea></label>`,'/api/courses'];
  if(kind==='section')return ['Create section',`<label>Course<select name="course_id">${cached.courses.map(c=>`<option value="${c.id}">${esc(c.code)} · ${esc(c.title)}</option>`).join('')}</select></label><label>Instructor<select name="instructor_id">${cached.instructors.map(i=>`<option value="${i.id}">${esc(i.name)}</option>`).join('')}</select></label><label>Term<input name="term" required value="Fall 2026"></label><label>Meeting days<select name="day"><option>Mon/Wed</option><option>Tue/Thu</option><option>Mon</option><option>Tue</option><option>Wed</option><option>Thu</option><option>Fri</option></select></label><label>Start time<input name="start_time" type="time" value="09:00" required></label><label>End time<input name="end_time" type="time" value="10:15" required></label><label>Room<input name="room" required placeholder="Science 101"></label><label>Capacity<input name="capacity" type="number" min="1" max="300" value="20" required></label>`,'/api/sections'];
  return ['New announcement',`<label class="wide">Section<select name="section_id">${sectionOptions(cached.sections)}</select></label><label class="wide">Title<input name="title" required maxlength="100"></label><label class="wide">Message<textarea name="body" required maxlength="1000"></textarea></label>`,'/api/announcements'];
}
document.addEventListener('click',async ev=>{
  const nav=ev.target.closest('[data-page]');if(nav){show(nav.dataset.page);return;}
  const modal=ev.target.closest('[data-modal]');if(modal){
    const [heading,fields,endpoint]=formTemplate(modal.dataset.modal);
    openModal(`<div class="eyebrow">CAMPUSFLOW</div><h2>${heading}</h2><form id="create-form" class="form-grid">${fields}<button class="primary">Save →</button></form>`);
    $('#create-form').onsubmit=async event=>{event.preventDefault();try{await post(endpoint,Object.fromEntries(new FormData(event.target)));closeModal();notify(heading+' saved.');refresh();}catch(error){notify(error.message);}};
    return;
  }
  const drop=ev.target.closest('[data-drop]');if(drop){
    if(!confirm('Drop this enrollment? The first eligible waitlisted student may be promoted.'))return;
    try{const d=await post('/api/enrollments/'+drop.dataset.drop+'/drop',{});notify(d.promoted_student_id?'Dropped; a waitlisted student was promoted.':'Enrollment dropped.');refresh();}catch(error){notify(error.message);}return;
  }
  const mark=ev.target.closest('[data-mark]');if(mark){
    try{await post('/api/attendance',{section_id:selectedSection,student_id:Number(mark.dataset.mark),class_date:$('#attendance-date').value,status:$('#mark-'+mark.dataset.mark).value});notify('Attendance saved.');drawAttendance();}catch(error){notify(error.message);}return;
  }
  const score=ev.target.closest('[data-score]');if(score){
    const [student_id,assessment_id]=score.dataset.score.split(':').map(Number);
    try{await post('/api/scores',{student_id,assessment_id,points:$('#score-'+student_id+'-'+assessment_id).value});notify('Score saved.');drawGrades();}catch(error){notify(error.message);}
  }
});
$('#close-modal').onclick=closeModal;
$('#modal-bg').onclick=ev=>{if(ev.target.id==='modal-bg')closeModal();};
document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closeModal();});
show('overview');
