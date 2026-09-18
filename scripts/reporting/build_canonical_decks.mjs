import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const root = "C:\\Users\\SabatiniLab\\Documents\\Codex\\2026-08-10\\i";
const build = path.join(root, "deck_update");
const out = path.join(build, "output");
const template = path.join(out, "photometry_per_session_standardized_through_20260916.pptx");
const skill = "C:\\Users\\SabatiniLab\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.909.11814\\skills\\presentations";
const python = "C:\\Users\\SabatiniLab\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const navy = "#19354D", muted = "#5B6770", pale = "#EAF0F4";

function addText(slide, text, position, style) {
  const box = slide.shapes.add({geometry:"textbox", position, fill:"none", line:{fill:"none",width:0}});
  box.text = text;
  box.text.style = {typeface:"Arial", autoFit:"shrinkText", ...style};
  return box;
}

async function baseDeck(title, subtitle) {
  const p = await PresentationFile.importPptx(await FileBlob.load(template));
  const old = [...p.slides.items];
  for (let i = old.length - 1; i >= 0; i--) old[i].delete();
  const s = p.slides.add({width:1280,height:720});
  s.background.fill = "#FFFFFF";
  s.shapes.add({geometry:"rect",position:{left:0,top:0,width:1280,height:18},fill:navy,line:{fill:"none",width:0}});
  addText(s,title,{left:72,top:190,width:1136,height:105},{fontSize:38,bold:true,color:navy,alignment:"center"});
  addText(s,subtitle,{left:145,top:320,width:990,height:90},{fontSize:20,color:muted,alignment:"center"});
  addText(s,"Analysis through 17 September 2026",{left:250,top:585,width:780,height:32},{fontSize:14,color:muted,alignment:"center"});
  return p;
}

async function figureSlide(p,title,subtitle,file,notes) {
  const s=p.slides.add({width:1280,height:720}); s.background.fill="#FFFFFF";
  addText(s,title,{left:44,top:18,width:1190,height:44},{fontSize:25,bold:true,color:navy});
  addText(s,subtitle,{left:44,top:62,width:1190,height:30},{fontSize:13,color:muted});
  const bytes=await fs.readFile(file);
  s.images.add({blob:bytes,contentType:"image/png",alt:title,fit:"contain",position:{left:35,top:94,width:1210,height:598}});
  s.speakerNotes.textFrame.setText(notes);
}

async function sectionSlide(p,title,subtitle) {
  const s=p.slides.add({width:1280,height:720}); s.background.fill="#FFFFFF";
  s.shapes.add({geometry:"rect",position:{left:0,top:0,width:1280,height:720},fill:pale,line:{fill:"none",width:0}});
  s.shapes.add({geometry:"rect",position:{left:0,top:0,width:26,height:720},fill:navy,line:{fill:"none",width:0}});
  addText(s,title,{left:100,top:235,width:1080,height:75},{fontSize:34,bold:true,color:navy});
  addText(s,subtitle,{left:102,top:325,width:1040,height:100},{fontSize:19,color:muted});
}

const sessions=[
  {label:"PS111 · 9/11",dir:"PS111_20260911_standardized",stem:"PS111_20260911_163909",note:"4970.5 s; 314 cues; 313 lick trials; 1 miss. R470 is the selected 470 channel for pooling; the left fiber was not connected."},
  {label:"PS113-2 · 9/11",dir:"PS113_2_20260911_standardized",stem:"PS113_2_20260911_192740",note:"7038.9 s; 480 cues; 462 lick trials; 18 misses."},
  {label:"PS113 · 9/14",dir:"PS113_20260914_standardized",stem:"PS113_20260914_143940",note:"4283.0 s; 307 cues; 306 lick trials; 1 miss."},
  {label:"PS113 · 9/15",dir:"PS113_20260915_analysis",stem:"PS113_20260915_110019",note:"4285.6 s; 360 cues; 308 lick trials; 52 misses, including the late no-lick block."},
  {label:"PS113 · 9/16",dir:"PS113_20260916_analysis",stem:"PS113_20260916_104941",note:"4504.8 s; 330 cues; 262 lick trials; 68 misses. Approximately 100 uW 470 excitation; 470 excluded from the selected pooled analysis."},
  {label:"PS113 · 9/17",dir:"PS113_20260917_analysis",stem:"PS113_20260917_104145",note:"5283.6 s; 480 cues; 333 lick trials; 147 misses. The 565 channels enter the selected pooled analysis. Both 9/17 470 channels remain excluded from pooling."},
];

const per=await baseDeck("Photometry: standardized per-session analyses","Consistent 200-Hz demodulated, rolling-z analyses for every recording; session-specific quality caveats retained");
for (const x of sessions) {
  await sectionSlide(per,x.label,x.note);
  const d=path.join(root,x.dir), s=x.stem;
  await figureSlide(per,`${x.label}: fast 470-nm lick responses`,"All licks versus first lick of bout; 200 Hz, 6-Hz display low-pass",path.join(d,`${s}_470_all_vs_first_bout_200Hz.png`),x.note);
  await figureSlide(per,`${x.label}: 470-nm responses by spout position`,"Near/far ipsi, middle and contra; all licks and first lick of bout",path.join(d,`${s}_470_by_position.png`),x.note);
  if (x.stem === "PS113_20260917_104145") {
    await figureSlide(per,`${x.label}: 470-nm reward-consumption lick response`,"First lick after reward; one event per rewarded consumption bout",path.join(d,`${s}_470_first_lick_after_reward_200Hz.png`),x.note+" This event is distinct from the first lick after a one-second quiet interval.");
    await figureSlide(per,`${x.label}: 470-nm reward-consumption lick by position`,"First lick after reward; near/far ipsi, middle and contra",path.join(d,`${s}_470_first_lick_after_reward_by_position.png`),x.note);
  }
  const missNote=(x.label==="PS111 · 9/11"||x.label==="PS113 · 9/14")?" Miss estimate n=1; display is descriptive and not a population estimate.":"";
  await figureSlide(per,`${x.label}: 565-nm cue response—lick versus miss`,"Cue-aligned traces overlaid within hemisphere"+((missNote)?"; miss n=1":""),path.join(d,`${s}_565_cue_lick_vs_miss_overlay.png`),x.note+missNote);
  await figureSlide(per,`${x.label}: 565-nm responses by spout position`,"Reward and first lick after reward; near/far ipsi, middle and contra",path.join(d,`${s}_565_by_position.png`),x.note);
}

const pooled=await baseDeck("Photometry: selected pooled analyses","Duration-weighted descriptive pools using prespecified high-quality channels and sessions");
await sectionSlide(pooled,"Selection rule","470 pool: PS111 R470 9/11 and PS113 L470 9/14-9/15. The 9/16 and 9/17 470 signals appear only in the per-session deck. The 565 pool includes both hemispheres from PS113-2 9/11 and PS113 9/14-9/17.");
const pd=path.join(root,"cross_session_20260914");
await figureSlide(pooled,"Selected 470-nm lick responses","All positions; all licks and first lick of bout",path.join(pd,"combined_470_all_positions.png"),"Duration-weighted descriptive mean. 9/16 470 excluded by data-quality decision.");
await figureSlide(pooled,"Selected 470-nm responses by relative position","Near/far ipsi, middle and contra",path.join(pd,"combined_470_relative_positions.png"),"Positions recoded relative to recorded hemisphere. 9/16 470 excluded.");
await figureSlide(pooled,"Selected 565-nm reward responses","All positions; reward and first lick after reward",path.join(pd,"combined_565_all_positions.png"),"L565 and R565 from 9/11 and 9/14-9/17; duration weighted. The 9/17 470 channels are excluded.");
await figureSlide(pooled,"Selected 565-nm responses by hemisphere and physical position","L and R hemispheres retained separately across near/far L, center and R positions",path.join(pd,"combined_565_physical_positions_by_hemisphere.png"),"Rows preserve recorded hemisphere and event definition. Columns retain physical spout position without ipsi/contra recoding. L/R y-scales match within reward and first-lick event families. Sessions 9/11 and 9/14-9/17; duration weighted.");
await figureSlide(pooled,"Selected 565-nm responses by relative position","Near/far ipsi, middle and contra",path.join(pd,"combined_565_relative_positions.png"),"Positions recoded relative to hemisphere; duration weighted.");
await figureSlide(pooled,"Trial-stop / spout-retraction response across sessions","565 rebound compared with simultaneous 470 artifact-control channels",path.join(root,"retraction_across_sessions","470_565_stop_aligned_artifact_control.png"),"Cross-session trial-stop alignment. Treat as a candidate biological response while retaining channel-specific motion/optical-coupling caveats.");

async function save(p,name) {
  const final=path.join(out,name); const stage=path.join(build,`.codex-finalizer-${path.parse(name).name}`);
  await fs.mkdir(stage,{recursive:true});
  const candidate=path.join(stage,"candidate.pptx");
  await (await PresentationFile.exportPptx(p)).save(candidate);
  const {finalizePresentation}=await import(pathToFileURL(path.join(skill,"container_tools/artifact_tool_utils.mjs")).href);
  await finalizePresentation({explicitTotalSlideCount:p.slides.items.length,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],workspaceDir:root,candidatePath:candidate,finalPath:final,pythonExecutable:python,integrityValidatorPath:path.join(skill,"container_tools/inspect_presentation_package_integrity.py"),layoutValidatorPath:path.join(skill,"container_tools/inspect_presentation_layout_geometry.py"),layoutArgs:["--expected-slide-size-emu","12192000,6858000","--validate-heading-fit"],verifyArtifactToolImport:true,receiptPath:path.join(stage,`${name}.validation.json`)});
  const montage=await p.export({format:"webp",montage:{columns:4,slideWidth:400,gap:10,padding:10},scale:.65});
  await fs.writeFile(path.join(build,`${path.parse(name).name}.montage.webp`),new Uint8Array(await montage.arrayBuffer()));
  console.log(JSON.stringify({final,slides:p.slides.items.length}));
}

await save(per,"photometry_per_session_standardized_through_20260917.pptx");
await save(pooled,"photometry_pooled_selected_through_20260917.pptx");
