public struct AnimatronicAnimationTask
{
    public AnimationType animation_type;
    public Animatronic animatronic;
    public float animation_time;
    public float coeff;
    public bool loop;
    public float animation_booster;

    public AnimatronicAnimationTask(
        AnimationType animation_type,
        float animation_time,
        float coeff,
        Animatronic animatronic,
        bool loop,
        float animation_booster
    )
    {
        this.animation_type = animation_type;
        this.animation_time = animation_time;
        this.coeff = coeff;
        this.loop = loop;
        this.animatronic = animatronic;
        this.animation_booster = animation_booster;
    }

    public string info()
    {
        return $"AnimatronicAnimationTask: animation_type: {animation_type}, animation_time: {animation_time}, coeff: {coeff}, loop: {loop}";
    }
}
