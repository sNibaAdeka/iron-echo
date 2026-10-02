#include "IEVisualCameraRig.h"
#include "Camera/CameraComponent.h"
#include "Components/SceneComponent.h"
#include "GameFramework/SpringArmComponent.h"

AIEVisualCameraRig::AIEVisualCameraRig()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickGroup=TG_PostPhysics;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("VisualRoot")));
    CameraArm=CreateDefaultSubobject<USpringArmComponent>(TEXT("ShoulderArm"));
    CameraArm->SetupAttachment(GetRootComponent());
    CameraArm->TargetArmLength=320.f;
    CameraArm->SocketOffset=FVector(0.f,65.f,0.f);
    CameraArm->bDoCollisionTest=true;
    CameraArm->ProbeSize=12.f;
    CameraArm->ProbeChannel=ECC_Camera;
    CameraArm->bEnableCameraLag=false;
    CameraArm->PrimaryComponentTick.TickGroup=TG_PostPhysics;
    CameraArm->AddTickPrerequisiteActor(this);
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(CameraArm,USpringArmComponent::SocketName);
    Camera->FieldOfView=75.f;
}

void AIEVisualCameraRig::FollowRobot(AActor* Robot,AActor* Opponent)
{
    if (AActor* Previous=FollowTarget.Get(); IsValid(Previous)) RemoveTickPrerequisiteActor(Previous);
    FollowTarget=Robot==this ? nullptr : Robot;
    LookTarget=Opponent==this ? nullptr : Opponent;
    bFirstFollow=true;
    if (IsValid(Robot) && Robot!=this) AddTickPrerequisiteActor(Robot);
    KickTime=0.f; KickStrength=0.f;
    Camera->SetRelativeLocation(FVector::ZeroVector);
}
void AIEVisualCameraRig::SetReducedMotion(bool Reduce)
{
    bReducedMotion=Reduce;
    if (Reduce) { KickTime=0.f; KickStrength=0.f; Camera->SetRelativeLocation(FVector::ZeroVector); }
}
void AIEVisualCameraRig::ApplyConfirmedContactKick(float Intensity)
{
    if (bReducedMotion || !FMath::IsFinite(Intensity)) return;
    KickTime=0.16f;
    KickStrength=FMath::Clamp(Intensity,0.f,1.f)*FMath::Clamp(ShakeScale,0.f,1.f)*1.5f;
}
void AIEVisualCameraRig::Tick(float Delta)
{
    Super::Tick(Delta);
    AActor* Robot=FollowTarget.Get();
    if (!IsValid(Robot)) { Camera->SetRelativeLocation(FVector::ZeroVector); return; }
    const FVector Anchor=Robot->GetActorTransform().TransformPosition(FollowOffset);
    FRotator Facing=Robot->GetActorRotation();
    if (AActor* Opponent=LookTarget.Get(); IsValid(Opponent))
        Facing=(Opponent->GetActorTransform().TransformPosition(OpponentAimOffset)-Anchor).Rotation();
    Facing.Roll=0.f;
    Facing.Pitch=FMath::Clamp(Facing.Pitch,-20.0,15.0);
    const float Speed=FMath::Max(1.f,FollowSpeed);
    SetActorLocation(bFirstFollow ? Anchor : FMath::VInterpTo(GetActorLocation(),Anchor,Delta,Speed));
    SetActorRotation(bFirstFollow ? Facing : FMath::RInterpTo(GetActorRotation(),Facing,Delta,Speed));
    bFirstFollow=false;
    KickTime=FMath::Max(0.f,KickTime-Delta);
    const float Fade=KickTime/.16f;
    Camera->SetRelativeLocation(FVector(0.f,0.f,bReducedMotion ? 0.f : FMath::Sin(Fade*PI*3.f)*Fade*KickStrength));
}
