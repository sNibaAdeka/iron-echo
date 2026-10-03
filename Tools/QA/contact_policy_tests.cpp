#include "IEContactPolicy.h"
#include <cstdlib>
#include <iostream>
#include <limits>

using namespace IronEchoPresentation;
static int Cases=0;
static void Require(bool Value,const char* Message)
{
    if (!Value) { std::cerr << "FAIL: " << Message << '\n'; std::exit(1); }
}
static FEventKey Key(std::uint32_t Value) { return {Value,0,0,0}; }

int main()
{
    const double NaN=std::numeric_limits<double>::quiet_NaN();
    const double Inf=std::numeric_limits<double>::infinity();
    {
        FReactionHold Hold;
        Require(!Hold.Accept({},1,1),"invalid event ID");
        Require(!Hold.Accept(Key(1),NaN,1),"NaN intensity");
        Require(!Hold.Accept(Key(1),Inf,1),"infinite intensity");
        Require(!Hold.Accept(Key(1),1,NaN),"NaN clock");
        Require(!Hold.Accept(Key(1),1,Inf),"infinite clock");
        Require(!Hold.Accept(Key(1),1,-1),"negative clock");
        Require(Hold.Accept(Key(1),1,1),"invalid input must not consume valid ID");
        ++Cases;
    }
    {
        FReactionHold Hold;
        Require(Hold.Accept(Key(1),1,10),"first delivery");
        Require(!Hold.Accept(Key(1),1,10.060),"duplicate delivery");
        Require(Hold.PlayRate(10.070)==1,"duplicate cannot extend reaction hold");
        ++Cases;
    }
    {
        FReactionHold Hold;
        for (std::uint32_t Id=1; Id<=10000; ++Id)
        {
            const double Now=100+Id*0.000001;
            Require(Hold.Accept(Key(Id),1,Now),"unique rapid delivery");
        }
        Require(Hold.PlayRate(100.080)==1,"burst must not keep reaction frozen");
        Require(Hold.Accept(Key(10001),1,100.100),"cooldown contact is still accepted");
        Require(Hold.PlayRate(100.100)==1,"100 ms recovery gap keeps clip moving");
        Require(Hold.Accept(Key(10002),1,100.200),"next reaction allowed after recovery");
        Require(Hold.PlayRate(100.201)==0,"new hold after recovery");
        ++Cases;
    }
    {
        for (double Intensity : {0.0001,0.5,1.0,999.0})
        {
            FReactionHold Hold;
            Require(Hold.Accept(Key(1),Intensity,20),"finite intensity");
            Require(Hold.PlayRate(20.001)==0,"positive contact starts hold");
            Require(Hold.PlayRate(20.066)==1,"every intensity releases within 65 ms");
        }
        FReactionHold Hold;
        Require(Hold.Accept(Key(1),0,20),"zero intensity is valid presentation data");
        Require(Hold.PlayRate(20)==1,"zero intensity cannot stop reaction");
        ++Cases;
    }
    {
        FReactionHold Hold;
        Hold.Accept(Key(1),1,30);
        Hold.SetReducedMotion(true);
        Require(Hold.PlayRate(30.010)==1,"reduced motion cancels current hold");
        Require(Hold.Accept(Key(2),1,31),"reduced motion still consumes ID");
        Hold.SetReducedMotion(false);
        Require(!Hold.Accept(Key(2),1,32),"toggling preference cannot replay event");
        Require(Hold.PlayRate(32)==1,"toggle cannot revive a cancelled hold");
        Hold.SetReducedMotion(true); Hold.Reset(); Hold.Accept(Key(1),1,40);
        Require(Hold.PlayRate(40.001)==1,"session reset preserves reduced motion");
        ++Cases;
    }
    {
        FEventHistory History;
        for (std::uint32_t Id=1; Id<=512; ++Id) Require(History.Accept(Key(Id)),"initial history fill");
        Require(History.Size()==512,"history storage bounded");
        Require(!History.Accept(Key(1)),"oldest ID still retained at capacity");
        Require(History.Accept(Key(513)),"next ID evicts oldest");
        Require(!History.Accept(Key(2)),"second oldest survives one eviction");
        Require(History.Accept(Key(1)),"evicted ID may replay: adapter needs session sequencing");
        for (std::uint32_t Id=514; Id<100000; ++Id) History.Accept(Key(Id));
        Require(History.Size()==512,"long match never expands history");
        History.Reset(); Require(History.Size()==0 && History.Accept(Key(1)),"explicit new session");
        ++Cases;
    }
    {
        FReactionHold Hold; Hold.Accept(Key(1),1,50);
        Require(Hold.PlayRate(NaN)==1 && Hold.PlayRate(Inf)==1,"invalid clock fails open");
        Require(Hold.PlayRate(49)==1,"clock rewind fails open");
        Require(Hold.PlayRate(500)==1,"long pause cannot leave stale hold");
        ++Cases;
    }
    {
        for (int Fps : {15,30,60,144})
        {
            FReactionHold Hold; Hold.Accept(Key(1),1,60);
            double FirstMovingFrame=0;
            for (int Frame=0; Frame<=Fps; ++Frame)
                if (Hold.PlayRate(60+double(Frame)/Fps)==1) { FirstMovingFrame=double(Frame)/Fps; break; }
            Require(FirstMovingFrame>=0.065 && FirstMovingFrame<=0.065+1.0/Fps,"release by first frame after deadline");
        }
        ++Cases;
    }
    {
        FCameraPulse Pulse; Pulse.Start(99,99,70);
        Require(Pulse.OffsetCm(70)==0,"pulse starts without instantaneous positional jump");
        for (int Sample=0; Sample<=1000; ++Sample)
            Require(std::abs(Pulse.OffsetCm(70+Sample*0.0002))<=1.5,"camera displacement bounded in cm");
        Require(Pulse.OffsetCm(70.161)==0,"pulse ends within 160 ms");
        Require(Pulse.OffsetCm(100)==0,"pulse expires while world delta is zero");
        Require(Pulse.OffsetCm(NaN)==0 && Pulse.OffsetCm(69)==0,"invalid/rewound pulse clock");
        Pulse.Reset(); Require(Pulse.OffsetCm(70.010)==0,"target loss/reduced motion clears pulse");
        ++Cases;
    }
    {
        FCameraPulse Pulse;
        Pulse.Start(NaN,1,1); Require(Pulse.OffsetCm(1.01)==0,"NaN pulse rejected");
        Pulse.Start(1,Inf,1); Require(Pulse.OffsetCm(1.01)==0,"infinite shake scale rejected");
        Pulse.Start(1,1,NaN); Require(Pulse.OffsetCm(1.01)==0,"invalid pulse start rejected");
        Pulse.Start(-1,1,1); Require(Pulse.OffsetCm(1.01)==0,"negative intensity clamped");
        Pulse.Start(1,0,1); Require(Pulse.OffsetCm(1.01)==0,"zero shake preference");
        ++Cases;
    }
    std::cout << "PASS: " << Cases << " portable contact-policy scenarios; Unreal module/UHT/runtime NOT tested.\n";
}
