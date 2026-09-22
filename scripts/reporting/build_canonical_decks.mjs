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
  addText(s,"Analysis through 22 September 2026",{left:250,top:585,width:780,height:32},{fontSize:14,color:muted,alignment:"center"});
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
  {label:"PS113 · 9/16",dir:"PS113_20260916_analysis",stem:"PS113_20260916_104941",note:"4504.8 s; 330 cues; 261 lick trials; 69 misses. Approximately 100 uW 470 excitation; 470 excluded from the selected pooled analysis."},
  {label:"PS113 · 9/17",dir:"PS113_20260917_analysis",stem:"PS113_20260917_104145",note:"5283.6 s; 480 cues; 333 lick trials; 147 misses. The 565 channels enter the selected pooled analysis. Both 9/17 470 channels remain excluded from pooling."},
  {label:"PS113 · 9/18",dir:"PS113_20260918_analysis",stem:"PS113_20260918_122842",note:"5979.2 s; 540 cues; 419 lick trials; 121 misses. Detector QC failed: normal DAC loopbacks but nearly absent 470 carriers and markedly reduced 565 carriers. Excluded from all pooled biological analyses."},
  {label:"PS113 · 9/21",dir:"PS113_20260921_analysis",stem:"PS113_20260921_105243",note:"6497.0 s; 600 cues; 391 lick trials; 209 misses. Detector QC passed. Both 565 channels enter the selected pooled analysis. Both 470 channels enter the all-lick pool only."},
  {label:"PS113 · 9/22",dir:"PS113_20260922_analysis",stem:"PS113_20260922_112325",note:"4528.4 s; 450 cues; 346 lick trials; 104 misses. Detector QC passed. Both 565 channels and both 470 channels enter the descriptive pooled analyses; 470 retains oscillation and position-dependence caveats."},
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
  if (x.stem === "PS113_20260921_105243") {
    await figureSlide(per,"PS113 9/21: cue response across behavioral epochs","Lick trials compared with no-lick trials in the middle and end epochs",path.join(d,`${s}_565_cue_epoch_comparison.png`),"Middle epoch: trials 157-283. End epoch: trials 544-600, excluding the isolated lick trial. Means use baseline-corrected rolling z-score and a 6-Hz display low-pass.");
    await figureSlide(per,"PS113 9/21: no-lick cue response by reward delivery","Actual reward TTL distinguishes rewarded and unrewarded no-lick trials",path.join(d,`${s}_565_cue_reward_comparison.png`),"Reward status comes from the recorded TTL between each cue and the next cue. The recorded status agrees with the preceding-six-trial lick rule on 598 of 600 trials.");
    await figureSlide(per,"PS113 9/21: cue outcome and reward timeline","Middle and end no-lick epochs with actual reward state",path.join(d,`${s}_cue_state_timeline.png`),"The main middle no-lick block spans trials 157-283. The late epoch spans trials 544-600 and contains one isolated lick trial at 589.");
  }
  if (x.stem === "PS113_20260922_112325") {
    await figureSlide(per,"PS113 9/22: terminal no-lick cue response","Terminal miss block begins at trial 374",path.join(d,`${s}_565_terminal_no_lick_overlay.png`),"Complete photometry windows retain 75 terminal misses. Miss trials remain separate from the default lick-trial 565 pool.");
    await figureSlide(per,"PS113 9/22: cue outcome timeline","Lick and no-lick trials across the session",path.join(d,`${s}_cue_outcome_timeline.png`),"The terminal no-lick block begins at trial 374. Trial_stop defines the response-window boundary.");
  }
}

const noLickDir=path.join(root,"565_no_lick_over_time");
for (const day of ["915","916","917","918","921","922"]) {
  const failed=day==="918";
  await figureSlide(per,`PS113 ${day.slice(0,1)}/${day.slice(1)}: no-lick 565 response over time`,
    "Amplitude versus session time and minutes since the last detected lick",
    path.join(noLickDir,`PS113_${day}_565_no_lick_over_time.png`),
    failed ? "QC failed and the session is excluded from pooling." :
      "Mean 0.05-0.75 s after cue, baseline corrected from -1.0 to -0.5 s. Gray points are intermittent misses; red points belong to the terminal no-lick block.");
}

const pooled=await baseDeck("Photometry: selected pooled analyses","Duration-weighted descriptive pools using prespecified high-quality channels and sessions");
await sectionSlide(pooled,"Selection rule","470 all-lick pool: PS111 R470 9/11, PS113 L470 9/14-9/15, and PS113 L470 + R470 9/21-9/22. The first-lick-of-bout pool adds 9/22 L470 + R470 to the original selected channels. The 565 pool includes both hemispheres from PS113-2 9/11 and PS113 9/14-9/17 and 9/21-9/22; 9/18 failed detector QC.");
const pd=path.join(root,"cross_session_20260914");
await figureSlide(pooled,"Selected 470-nm lick responses","All positions; 9/22 L + R included for all licks and first lick of bout",path.join(pd,"combined_470_all_positions.png"),"Duration-weighted descriptive mean. The all-lick pool includes 9/21 and 9/22 L470 and R470. The first-lick-of-bout pool adds 9/22 L470 and R470; structured oscillation and position dependence remain caveats.");
await figureSlide(pooled,"Selected 470-nm responses by relative position","Near/far ipsi, middle and contra; event-specific channel selection",path.join(pd,"combined_470_relative_positions.png"),"Positions recoded relative to recorded hemisphere. The all-lick row includes 9/21 and 9/22 L470 and R470; the first-bout row adds 9/22 L470 and R470.");
await figureSlide(pooled,"Selected 565-nm reward responses","All positions; reward and first lick after reward",path.join(pd,"combined_565_all_positions.png"),"L565 and R565 from 9/11, 9/14-9/17 and 9/21-9/22; duration weighted. The 9/18 session failed detector QC. Only trials with consummatory licks enter the default pool.");
await figureSlide(pooled,"Selected 565-nm responses by hemisphere and physical position","L and R hemispheres retained separately across near/far L, center and R positions",path.join(pd,"combined_565_physical_positions_by_hemisphere.png"),"Rows preserve recorded hemisphere and event definition. Columns retain physical spout position without ipsi/contra recoding. L/R y-scales match within reward and first-lick event families. Sessions 9/11, 9/14-9/17 and 9/21; duration weighted.");
await figureSlide(pooled,"Selected 565-nm responses by relative position","Near/far ipsi, middle and contra",path.join(pd,"combined_565_relative_positions.png"),"Positions recoded relative to hemisphere; duration weighted.");
await figureSlide(pooled,"Trial-stop / spout-retraction response across sessions","565 rebound compared with simultaneous 470 artifact-control channels; includes 9/21 and 9/22",path.join(root,"retraction_across_sessions","470_565_stop_aligned_artifact_control.png"),"Cross-session trial-stop alignment through 9/22. R565 shows an upward post-stop rebound on 9/21 and 9/22; L565 remains flat or slightly negative. Simultaneous 470 channels lack a comparably consistent rebound. Treat this as a candidate biological response while retaining motion and optical-coupling caveats.");
await figureSlide(pooled,"565 response after licking stops","No systematic decline across valid terminal no-lick blocks",path.join(noLickDir,"pooled_565_terminal_no_lick_response_over_time.png"),"L/R averaged within session, then sessions weighted equally in two-minute bins. Included: 9/15-9/17 and 9/22. The 9/18 amplifier-failure session is excluded; 9/21 has only nine complete terminal-block windows.");
await figureSlide(pooled,"Early and late terminal misses differ across sessions","First 10 versus last 10 misses in each qualifying terminal block",path.join(noLickDir,"pooled_565_terminal_no_lick_first10_vs_last10.png"),"L/R averaged within trial, then the first and last ten terminal misses compared within each session. Changes were +0.10 z on 9/15, +0.21 z on 9/16, -0.10 z on 9/17, and +0.31 z on 9/22. Thus 9/22 increased rather than declined. 9/21 has only nine complete terminal-block windows.");

async function save(p,name) {
  const final=path.join(out,name); const stage=path.join(build,`.codex-finalizer-${path.parse(name).name}-0922-retraction`);
  await fs.mkdir(stage,{recursive:true});
  const candidate=path.join(stage,"candidate.pptx");
  await (await PresentationFile.exportPptx(p)).save(candidate);
  const {finalizePresentation}=await import(pathToFileURL(path.join(skill,"container_tools/artifact_tool_utils.mjs")).href);
  await finalizePresentation({explicitTotalSlideCount:p.slides.items.length,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],workspaceDir:root,candidatePath:candidate,finalPath:final,pythonExecutable:python,integrityValidatorPath:path.join(skill,"container_tools/inspect_presentation_package_integrity.py"),layoutValidatorPath:path.join(skill,"container_tools/inspect_presentation_layout_geometry.py"),layoutArgs:["--expected-slide-size-emu","12192000,6858000","--validate-heading-fit"],verifyArtifactToolImport:true,receiptPath:path.join(stage,`${name}.validation.json`)});
  const montage=await p.export({format:"webp",montage:{columns:4,slideWidth:400,gap:10,padding:10},scale:.65});
  await fs.writeFile(path.join(build,`${path.parse(name).name}.montage.webp`),new Uint8Array(await montage.arrayBuffer()));
  console.log(JSON.stringify({final,slides:p.slides.items.length}));
}

await save(per,"photometry_per_session_standardized_through_20260922.pptx");
await save(pooled,"photometry_pooled_selected_through_20260922.pptx");
