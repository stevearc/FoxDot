SynthDef.new(\blip,
{|amp=1, sus=1, pan=0, freq=0, vib=0, fmod=0, rate=0, bus=0|
var osc, env;
freq = In.kr(bus, 1);
freq = [freq, freq+fmod];
amp=(amp + 1e-05);
freq=[freq, (freq + LFNoise2.ar(50).range(-2, 2))];
freq=(freq * 2);
osc=((LFCub.ar((freq * 1.002), iphase: 1.5) + (LFTri.ar(freq, iphase: Line.ar(2, 0, 0, 2)) * 0.3)) * Blip.ar((freq / 2), rate));
osc=((osc * XLine.ar(amp, (amp / 10000), (sus * 2))) * 0.3);
osc = Mix(osc) * 0.5;
osc = Pan2.ar(osc, pan);
	ReplaceOut.ar(bus, osc)}).add;
