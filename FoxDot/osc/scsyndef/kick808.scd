SynthDef.new(\kick808,
{|vib=0, rate=0, sus=1, fmod=0, bus=0, amp=1, freq=0, pan=0|
var osc, env;
freq = In.kr(bus, 1);
freq = [freq, freq+fmod];
osc=Ringz.ar(Impulse.ar(0), XLine.ar(240, 60, 0.1), sus, amp);
env=EnvGen.ar(Env.perc(level: amp,curve: 0,attackTime: 0.001,releaseTime: sus), doneAction: 2);
osc=(osc * env);
osc = Mix(osc) * 0.5;
osc = Pan2.ar(osc, pan);
	ReplaceOut.ar(bus, osc)}).add;
