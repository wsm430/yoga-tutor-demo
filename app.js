const poses = document.querySelector('#pose');
const preview = document.querySelector('#pose-preview');
const poseImage = document.querySelector('#pose-image');
const previewName = document.querySelector('#preview-name');
const video = document.querySelector('#camera');
const empty = document.querySelector('#camera-empty');
const scan = document.querySelector('#scan');
const hold = document.querySelector('#hold');
const holdValue = document.querySelector('#hold-value');
const poseTag = document.querySelector('#pose-tag');
const cameraButton = document.querySelector('#camera-button');
const demoButton = document.querySelector('#demo-button');
const error = document.querySelector('#error');
let stream = null;
let evaluated = false;

const jointData = [['左肩',92,108],['右肩',91,74],['左肘',164,151],['右肘',170,165],['左髋',128,142],['右髋',132,129],['左膝',118,93],['右膝',171,168]];
function drawJoints(active=false){document.querySelector('#joints').innerHTML=jointData.map(([name,current,target],index)=>{const diff=current-target,ok=Math.abs(diff)<=(index<4?20:25);return `<div class="joint-row"><span class="status ${ok?'ok':'warn'}">${ok?'✓':'!'}</span><strong>${name}</strong><span class="angle">${active?current+'°':'—'}</span><span class="target">标准 ${target}°</span><span class="delta ${ok?'ok-text':''}">${active?(diff>0?'+':'')+diff+'°':'—'}</span></div>`}).join('')}
function setPreview(){const file=`poses/${encodeURIComponent(poses.value)}.jpg`;poseImage.src=file;poseImage.alt=`${poses.value} 标准姿势参考`;previewName.textContent=poses.value;poseTag.querySelector('span').textContent=poses.value}
drawJoints();setPreview();poses.addEventListener('change',setPreview);
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-mode]').forEach(x=>x.classList.remove('active'));button.classList.add('active');const manual=button.dataset.mode==='manual';poses.disabled=!manual;preview.querySelector('.preview-mode').textContent=manual?'当前标准参考':'自动候选参考';preview.querySelector('small').textContent=manual?'请参照图中姿势调整身体位置与关节角度':'请让全身进入画面，系统会匹配最接近的标准姿势'}));
cameraButton.addEventListener('click',async()=>{if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;empty.hidden=false;scan.hidden=true;cameraButton.textContent='开启摄像头';cameraButton.className='button primary';document.querySelector('#camera-dot').classList.remove('live');return}try{stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});video.srcObject=stream;empty.hidden=true;scan.hidden=false;cameraButton.textContent='关闭摄像头';cameraButton.className='button outline';document.querySelector('#camera-dot').classList.add('live');error.textContent=''}catch(e){error.textContent='无法访问摄像头。请通过本地服务器打开并允许权限；演示评估仍可使用。'}});
demoButton.addEventListener('click',()=>{evaluated=false;hold.hidden=false;poseTag.hidden=true;let progress=0;const timer=setInterval(()=>{progress+=2;holdValue.textContent=progress+'%';if(progress>=100){clearInterval(timer);hold.hidden=true;poseTag.hidden=false;evaluated=true;document.querySelector('#score').innerHTML='82<sup>/100</sup>';document.querySelector('#score-state').textContent='评估完成';document.querySelector('#score-bar').style.width='82%';document.querySelector('#score-copy').textContent='动作整体良好，优先调整左膝与左肩。';demoButton.textContent='重新评估';drawJoints(true);document.querySelector('.haptic .motor.up').classList.add('active');document.querySelectorAll('.haptic .motor.left')[1].classList.add('active')}},40)});
