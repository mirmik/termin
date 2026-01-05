using System;
using System.Collections.Generic;
using UnityEngine;

public struct TState
{
    public ObjectOfTimeline obj;
    public PatrolState state;

    public TState(ObjectOfTimeline obj, PatrolState state)
    {
        this.obj = obj;
        this.state = state;
    }
}

public class GuardReactionCommander : BasicAiCommander
{
    string last_seen_hero_id = "";

    public GuardReactionCommander() : base() { }

    public override string Info()
    {
        string buf = "GuardReactionCommander: ";
        buf += base.Info() + "\n";
        buf += "last_seen_hero_id: " + last_seen_hero_id + "\n";
        return buf;
    }

    ObjectOfTimeline StimulPhaseHeroes(ObjectOfTimeline actor, ITimeline timeline)
    {
        bool founded = false;
        MyList<ObjectOfTimeline> heroes = timeline.Heroes();
        ObjectOfTimeline last_seen_hero = null;

        if (last_seen_hero_id != "" && last_seen_hero_id != null)
        {
            last_seen_hero = timeline.GetActor(last_seen_hero_id);

            if (last_seen_hero != null)
            {
                if (last_seen_hero.IsDead)
                {
                    last_seen_hero_id = "";
                    last_seen_hero = null;
                }
                else
                {
                    Actor hero = timeline.GetActor(last_seen_hero_id);
                    bool is_visible = TestHero(actor, hero);
                    if (is_visible)
                    {
                        founded = true;
                        return hero;
                    }
                }
            }
        }

        foreach (var hero in heroes)
        {
            if (!(hero is Actor))
                continue;

            if (hero == last_seen_hero)
                continue;

            if (hero.IsDead)
                continue;

            bool is_visible = TestHero(actor, hero);
            if (is_visible)
            {
                founded = true;
                last_seen_hero_id = hero.Name();
                last_seen_hero = hero;
                break;
            }
        }

        if (!founded)
        {
            return null;
        }
        else
        {
            return last_seen_hero;
        }
    }

    public bool ReactionToAlarmSource(
        ObjectOfTimeline actor,
        AlarmSource alarm_source,
        long local_step,
        ITimeline timeline
    )
    {
        var source_position = alarm_source.Center(timeline);
        var current_animatronic = actor.CurrentAnimatronic();
        bool high_level_alarm = alarm_source.IsHighLevelAlarm();
        bool is_corpse_reaction = alarm_source.IsCorpseReaction();

        if (alarm_source is LoudSoundAlarmSource)
        {
            return LoudSoundAlarmSourceReaction(
                actor,
                alarm_source as LoudSoundAlarmSource,
                local_step,
                timeline
            );
        }
        else if (alarm_source is FoundCorpseAlarmSource)
        {
            return CorpseAlarmSourceReaction(
                actor,
                alarm_source as FoundCorpseAlarmSource,
                local_step,
                timeline
            );
        }
        else if (alarm_source is FoundInterestAlarmSource)
        {
            return InterestAlarmSourceReaction(
                actor,
                alarm_source as FoundInterestAlarmSource,
                local_step,
                timeline
            );
        }
        else
            Debug.LogError("Unknown alarm source type" + alarm_source.GetType());

        return false;
    }

    bool TestHero(ObjectOfTimeline actor, ObjectOfTimeline hero)
    {
        bool is_visible =
            actor.GetTimeline().IsCanSee(actor._timeline_index, hero._timeline_index) == CanSee.See;

        return is_visible;
    }

    public TState EvalRedReaction(
        BasicAiController aicontroller,
        ObjectOfTimeline obj,
        PatrolState state,
        bool very_small
    )
    {
        var actor = aicontroller.GetObject();
        var pos = actor.GlobalPosition();
        float distruct_level = aicontroller._distruct_state.Level(actor.LocalStep());

        if (!aicontroller.IsDistruct())
        {
            aicontroller.StartDistruct(very_small);
        }

        float distance = Vector3.Distance(pos, obj.GlobalPosition());
        if (distance < distruct_level)
        {
            if (!aicontroller.IsRedDistruct())
                aicontroller.RedDistruct();
            return new TState(obj, state);
        }

        return new TState(obj, PatrolState.None);
    }

    TState EvalVioletReaction(
        BasicAiController aicontroller,
        ObjectOfTimeline obj,
        PatrolState state
    )
    {
        var actor = aicontroller.GetObject();
        var pos = actor.GlobalPosition();
        float distruct_level = aicontroller._distruct_state.Level(actor.LocalStep());

        if (!aicontroller.IsDistruct())
        {
            aicontroller.StartDistruct(false);
        }

        float distance = Vector3.Distance(pos, obj.GlobalPosition());
        if (distance < distruct_level)
        {
            if (!aicontroller.IsVioletDistruct())
                aicontroller.VioletDistruct();
            return new TState(obj, state);
        }

        return new TState(obj, PatrolState.None);
    }

    TState StimulPhase(BasicAiController aicontroller, ITimeline timeline)
    {
        var actor = aicontroller.GetObject();
        var pos = actor.GlobalPosition();
        float distruct_level = aicontroller._distruct_state.Level(actor.LocalStep());
        bool distructed = false;
        ObjectOfTimeline obj;

        obj = StimulPhaseHeroes(aicontroller.GetObject(), timeline);
        if (obj != null)
        {
            distructed = true;
            var r = EvalRedReaction(
                aicontroller,
                obj,
                PatrolState.Attack,
                very_small: obj.IsVerySmall()
            );
            if (r.state != PatrolState.None)
                return r;
        }

        obj = StimulPhaseColeagues(actor, timeline);
        if (obj != null)
        {
            distructed = true;
            var r = EvalRedReaction(aicontroller, obj, PatrolState.Panic, false);
            if (r.state != PatrolState.None)
                return r;
        }

        obj = StimulLureObjects(actor, timeline);
        if (obj != null)
        {
            distructed = true;
            var r = EvalVioletReaction(aicontroller, obj, PatrolState.Interested);
            if (r.state != PatrolState.None)
                return r;
        }

        if (!distructed)
        {
            if (aicontroller.IsDistruct() && !aicontroller.attention_module.IsPanic())
            {
                aicontroller.StopDistruct();
            }
        }

        return new TState(null, PatrolState.None);
    }

    public override BasicAiCommander Copy()
    {
        GuardReactionCommander buf = new GuardReactionCommander();
        buf.CopyFrom(this);
        return buf;
    }

    public override void CopyFrom(BasicAiCommander other_)
    {
        var other = (GuardReactionCommander)other_;
        base.CopyFrom(other);
        last_seen_hero_id = other.last_seen_hero_id;
        //loudSoundSource = other.loudSoundSource;
    }

    ObjectOfTimeline StimulPhaseColeagues(ObjectOfTimeline actor, ITimeline timeline)
    {
        MyList<ObjectOfTimeline> coleagues = timeline.Enemies();

        foreach (var coleague in coleagues)
        {
            if (!coleague.IsDead && !coleague.IsPreDead)
                continue;

            bool is_visible = TestHero(actor, coleague);
            if (is_visible)
            {
                return coleague;
            }
        }
        return null;
    }

    ObjectOfTimeline StimulLureObjects(ObjectOfTimeline actor, ITimeline timeline)
    {
        MyList<LureComponent> lst = (timeline as Timeline).present.LureComponentsCache();

        foreach (var lure_component in lst)
        {
            //var lure_component = lure.GetComponent<LureComponent>();
            if (lure_component == null)
                continue;

            if (!lure_component.LureEnabled())
                continue;

            var lure = lure_component.Owner;
            bool is_visible = TestHero(actor, lure);
            if (is_visible)
            {
                return lure;
            }
        }
        return null;
    }

    void AtackPhase2(ObjectOfTimeline actor, ObjectOfTimeline hero, ITimeline timeline)
    {
        var shoot_ability = actor.GetAbility<ShootAbility>();
        if (shoot_ability == null)
        {
            //Debug.Log("Warning!!!: Must Use Shoot ability but it is null");
            return;
        }

        var current_active_command = actor.CurrentCommand();
        if (current_active_command is ShootCommand)
            return;

        bool can_use = shoot_ability.CanUse(timeline, actor.AbilityListPanel());
        if (!can_use)
            return;

        if (shoot_ability != null)
        {
            shoot_ability.UseOnObject(hero, timeline, actor.AbilityListPanel());
        }
    }

    bool LoudSoundAlarmSourceReaction(
        ObjectOfTimeline actor,
        LoudSoundAlarmSource alarm_source,
        long local_step,
        ITimeline timeline
    )
    {
        if (!alarm_source.Lures)
        {
            return LoudSoundNonLuresReaction(actor, alarm_source, local_step, timeline);
        }
        else
        {
            return LoudSoundLuresReaction(actor, alarm_source, local_step, timeline);
        }
    }

    bool LoudSoundLuresReaction(
        ObjectOfTimeline actor,
        LoudSoundAlarmSource alarm_source,
        long local_step,
        ITimeline timeline
    )
    {
        var source_position = alarm_source.Center(timeline);
        var current_animatronic = actor.CurrentAnimatronic();
        bool high_level_alarm = alarm_source.IsHighLevelAlarm();

        if (current_animatronic is IdleAnimatronic || current_animatronic == null)
        {
            var current_position = actor.GlobalPosition();
            if (Vector3.Distance(current_position, source_position.GlobalPosition(timeline)) > 1.0f)
            {
                (actor as Actor).MoveToCommand(
                    source_position,
                    high_level_alarm ? WalkingType.Run : WalkingType.Walk
                );
            }
        }

        var last_animatronic = actor.LastAnimatronic;
        if (
            (
                last_animatronic.FinalPose(timeline).ToPoint().GlobalPosition(timeline)
                - source_position.GlobalPosition(timeline)
            ).magnitude > 1.0f
        )
        {
            (actor as Actor).MoveToCommand(
                source_position,
                high_level_alarm ? WalkingType.Run : WalkingType.Walk
            );
        }

        return true;
    }

    bool InterestAlarmSourceReaction(
        ObjectOfTimeline actor,
        FoundInterestAlarmSource alarm_source,
        long local_step,
        ITimeline timeline
    )
    {
        var source_position = alarm_source.Center(timeline);
        var current_animatronic = actor.CurrentAnimatronic();
        bool high_level_alarm = alarm_source.IsHighLevelAlarm();

        if (current_animatronic is IdleAnimatronic || current_animatronic == null)
        {
            var current_position = actor.GlobalPosition();
            if (Vector3.Distance(current_position, source_position.GlobalPosition(timeline)) > 1.0f)
            {
                (actor as Actor).MoveToCommand(
                    source_position,
                    high_level_alarm ? WalkingType.Run : WalkingType.Walk
                );
            }
        }

        var last_animatronic = actor.LastAnimatronic;
        if (
            (
                last_animatronic.FinalPose(timeline).ToPoint().GlobalPosition(timeline)
                - source_position.GlobalPosition(timeline)
            ).magnitude > 1.0f
        )
        {
            (actor as Actor).MoveToCommand(
                source_position,
                high_level_alarm ? WalkingType.Run : WalkingType.Walk
            );
        }

        return true;
    }

    bool CorpseAlarmSourceReaction(
        ObjectOfTimeline actor,
        AlarmSource alarm_source,
        long local_step,
        ITimeline timeline
    )
    {
        var source_position = alarm_source.Center(timeline);
        var current_animatronic = actor.CurrentAnimatronic();
        bool high_level_alarm = alarm_source.IsHighLevelAlarm();
        bool is_corpse_reaction = alarm_source.IsCorpseReaction();

        {
            // TODO: Заменить на код, который не будет выполняться на каждой итерации.
            // Скорее всего надо вынести в поведение более выскокого уровня
            var strtpos = actor.GlobalPosition();
            var tgtpos = source_position.GlobalPosition(timeline);
            //PlatformAreaBase platform;
            var testpath = PathFinding.RawPathFinding(
                strtpos,
                tgtpos,
                actor.NavArea()
            //, out platform
            );

            if (testpath.status != UnityEngine.AI.NavMeshPathStatus.PathComplete)
            {
                return true;
            }
        }

        if (current_animatronic is IdleAnimatronic || current_animatronic == null)
        {
            var current_position = actor.GlobalPosition();
            if (Vector3.Distance(current_position, source_position.GlobalPosition(timeline)) > 1.0f)
            {
                if ((actor as Actor) == null)
                    return true;

                (actor as Actor).MoveToCommand(
                    source_position,
                    high_level_alarm ? WalkingType.Run : WalkingType.Walk
                );
            }
        }

        var last_animatronic = actor.LastAnimatronic;
        //var current_moving = last_animatronic as MovingAnimatronic;
        if (
            (
                last_animatronic.FinalPose(timeline).ToPoint().GlobalPosition(timeline)
                - source_position.GlobalPosition(timeline)
            ).magnitude > 1.0f
        )
        {
            (actor as Actor).MoveToCommand(
                source_position,
                high_level_alarm ? WalkingType.Run : WalkingType.Walk
            );
        }

        return true;
    }

    bool LoudSoundNonLuresReaction(
        ObjectOfTimeline actor,
        LoudSoundAlarmSource alarm_source,
        long local_step,
        ITimeline timeline
    )
    {
        var current_animatronic = actor.CurrentAnimatronic();

        if (current_animatronic is RotateAnimatronic)
        {
            var current_rotate = current_animatronic as RotateAnimatronic;
            if (current_rotate.TargetPosition == alarm_source.Center(timeline))
                return true;
        }

        (actor as Actor).SightToCommand(alarm_source.Center(timeline), stamp: local_step);
        return true;
    }

    public void AddFoundedColleagueCorpse(BasicAiController actor, ObjectOfTimeline founded_actor)
    {
        var step = actor.GetObject().LocalStep();
        actor.AddCard(new CorpseFoundStateEvent(step: step, corpse_id: founded_actor.ObjectId()));
    }

    public void AddFoundedInterest(BasicAiController aicontroller, ObjectOfTimeline founded)
    {
        // Debug.Log("AddFoundedInterest");
        // actor.AddCard(
        // 	new InterestFoundStateEvent(
        // 		step: actor.GetObject().LocalStep(),
        // 		object_id: founded.ObjectId())
        // );
        var attention_module = aicontroller.AttentionModule();
        attention_module.FoundInterest(aicontroller.GetObject().LocalStep(), founded.ObjectId());
    }

    public void DisableLureIfNeed(BasicAiController actor, ObjectOfTimeline founded)
    {
        var lure = founded.GetComponent<LureComponent>();
        if (lure == null)
            return;

        if (lure.LureEnabled())
            lure.AddDisableLureEvent(actor.GetObject().LocalStep());
    }

    public override bool WhatIShouldDo(
        BasicAiController aicontroller,
        long timeline_step,
        long local_step
    )
    {
        var actor = aicontroller.GetObject();
        var timeline = aicontroller.GetObject().GetTimeline();

        var ts = StimulPhase(aicontroller, timeline);
        var founded_actor = ts.obj;
        var behaviour = ts.state;

        if (behaviour == PatrolState.Attack && founded_actor != null)
        {
            AtackPhase2(actor, founded_actor, timeline);
            return true;
        }

        var attention_module = aicontroller.AttentionModule();
        if (behaviour == PatrolState.Panic && founded_actor != null)
        {
            if (!attention_module.IsSeenCorpseEarly(founded_actor))
                AddFoundedColleagueCorpse(aicontroller, founded_actor);
        }

        if (behaviour == PatrolState.Interested && founded_actor != null)
        {
            AddFoundedInterest(aicontroller, founded_actor);
            DisableLureIfNeed(aicontroller, founded_actor);
        }

        if (attention_module.IsPanic())
        {
            var alarm_source = attention_module.LastAlarmSource();
            bool prevent = ReactionToAlarmSource(actor, alarm_source, local_step, timeline);
            if (prevent)
                return true;
        }

        return false;
    }
}
