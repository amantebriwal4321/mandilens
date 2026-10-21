# MandiLens video script

Target length: 4 minutes 30 seconds. Hard stop: 5 minutes 00 seconds.
Record 1080p, landscape. One take is fine if the cuts are clean.
Aman is on camera for the open and the close. The middle is screen recording with his voice.
Do not say the painted tray numbers are from a real mandi.

## 0:00 to 0:15  On camera

Frame: head and shoulders, decent light, the tray and the printed marker on the table beside you if you have them. Say this yourself, out loud:

"I am Aman Tebriwal. This is MandiLens, my solo entry. I am a CSE student in Bengaluru. The problem is grading tomatoes at a small mandi."

If you stumble, keep the name and "solo entry" in the first sentence. That is the part that shows the team.

## 0:15 to 0:45  The problem

Cut to the tray, or to a still of the morning sample if you have not shot fruit yet.

"At the stall, a lot is graded by eye in a few seconds. The farmer cannot argue with it, and damaged fruit often gets dumped instead of sent to processing. I wanted a phone photo and a printed 50 mm marker to measure each tomato, and to refuse the photo when the shot is bad."

Show the marker. Point at the black square. "This square is 50 mm. Not the white border."

## 0:45 to 1:40  A bad shot, then a good one

Screen: MandiLens in the browser, on a phone or a narrow window.

Click "Soft focus". Wait for the slip.

"The blur score is under 80. The agent sharpens once, looks again, and the score is still bad. It asks for a retake and it does not grade anything. The trace is on the right."

Then click "Morning lot".

"Same tray, sharp photo. OpenCV 5 finds the marker, splits the two tomatoes that touch, and reports diameter in millimetres, ripeness, defect, and a house grade. A, B, or C. These bands are mine. They are not an AGMARK grade. This mix is mostly B with one C, so the lot goes to local retail, not the wholesale mandi."

Scroll the fruit table and the trace so both are readable for a couple of seconds.

## 1:40 to 2:20  Dark shot, then a person

Click "Too dark".

"This one is underexposed. Brightness is under 85, so the agent lifts gamma and inspects again. The second inspect passes, and then it grades. A single pass would have refused the photo. The vision numbers picked the next tool."

Click "Cut off fruit".

"One tomato is clipped by the frame. Confidence drops under 0.70, so the agent will not route. I override that fruit to C."

Change the dropdown to C, click "Save review and route".

"The route changes. Accepting it would have sent the lot to the mandi. Overriding it to C sends it to local retail. That decision is a step in the trace."

## 2:20 to 3:05  Architecture

Full screen `docs/architecture.png`, then `docs/agent_flow.png`.

"OpenCV 5 does the actual seeing: quality gate, ArUco scale, chroma mask, watershed when fruit touch, then diameter, hue, and defect. That library is version 5, headless, on the Lambda layer too."

"On AWS the photo hits API Gateway, then an arm64 Lambda. Uploads sit in a private S3 bucket and die after 7 days. The lot and the trace go to DynamoDB. CloudWatch gets the logs. Bedrock can drive the same tools, and it is off until the account has the model. The tested planner is the rule one, and it calls the same tools. The template is SAM. `sam validate` passes. I have not deployed it in this video."

Optional: flash `docs/eval/traces/dark.json` for two seconds so the gamma step is visible as JSON.

## 3:05 to 4:05  Results, including a failure

Show `docs/eval/results.json` or a slide with these figures, and say them:

"On 24 painted trays, 114 tomatoes, every fruit was counted. Diameter error averages 0.29 millimetres. Grade and ripeness both matched the paint on all 114. The quality gate caught 5 bad shots and kept 8 good ones."

"Against a single inspect, the agent handled 14 of 14 scripted cases. The single pass missed 2: the dark photo, and the cut off fruit it would have routed without asking."

Cut to `docs/eval/red_tray.jpg`.

"This is a failure I kept. Red tray, red tomatoes. The mask cannot see them, median chroma is way over the cutoff, and the agent asks for a plain tray. It does not invent a grade. These numbers are from painted circles, not from a stall. I still need ruler measurements on real fruit before I quote a field error."

## 4:05 to 4:30  Close, on camera

Back to your face.

"Limits: shoot from above, plain light tray, and do not treat the grade as official. Photos on AWS expire after 7 days. Next is a real tray, a ruler, and more crops. That is MandiLens."

Stop. If you are over 4:30, cut the JSON flash and the second architecture sentence before you cut the on camera close.
