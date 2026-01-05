// #if UNITY_64
// using UnityEngine;
// #endif

// using System.Collections.Generic;
// using System;

// public struct ReferencedVelocity : IEquatable<ReferencedVelocity>
// {
//     public Vector3 LocalVelocity;
//     public ObjectId Frame;
//     public ObjectId FrameHash => Frame;

//     public ReferencedVelocity(Vector3 velocity, string frame)
//     {
//         this.LocalVelocity = velocity;
//         this.Frame = new ObjectId(frame);
//     }

//     public ReferencedVelocity(Vector3 velocity, ObjectId frame)
//     {
//         this.LocalVelocity = velocity;
//         this.Frame = frame;
//     }

//     public ReferencedVelocity(ReferencedVelocity other) : this(other.LocalVelocity, other.Frame) { }

//     public override string ToString()
//     {
//         return string.Format("ReferencedVelocity({0}, {1})", LocalVelocity, Frame);
//     }

//     // equality
//     public bool Equals(ReferencedVelocity other)
//     {
//         return LocalVelocity == other.LocalVelocity && Frame == other.Frame;
//     }

//     public override bool Equals(object obj)
//     {
//         if (obj == null || GetType() != obj.GetType())
//         {
//             return false;
//         }
//         return Equals((ReferencedVelocity)obj);
//     }

//     public override int GetHashCode()
//     {
//         if (Frame == default(ObjectId))
//         {
//             return LocalVelocity.GetHashCode();
//         }
//         return LocalVelocity.GetHashCode() ^ Frame.GetHashCode();
//     }

//     // operators
//     static public bool operator ==(ReferencedVelocity a, ReferencedVelocity b)
//     {
//         return a.Equals(b);
//     }

//     static public bool operator !=(ReferencedVelocity a, ReferencedVelocity b)
//     {
//         return !a.Equals(b);
//     }

//     public Vector3 GlobalVelocity(ITimeline tl)
//     {
//         if (Frame == default(ObjectId))
//         {
//             return LocalVelocity;
//         }

//         var frame_velocity = tl.GetVelocityScrew(FrameHash);
//         var frame_pose = tl.GetFrame(FrameHash);
//         return frame_pose.TransformVector(LocalVelocity) + frame_velocity.GlobalVelocity(tl);
//     }

//     public float DistanceTo(ReferencedVelocity other, ITimeline tl)
//     {
//         return Vector3.Distance(GlobalVelocity(tl), other.GlobalVelocity(tl));
//     }

//     public static ReferencedVelocity FromGlobalVelocity(Vector3 velocity, ObjectId frame, ITimeline tl)
//     {
//         var global_frame_velocity = tl.GetVelocity(frame).GlobalVelocity(tl);
//         var local_velocity = tl.GetFrame(frame)
//             .InverseTransformVector(velocity - global_frame_velocity);
//         return new ReferencedVelocity(local_velocity, frame);
//     }

//     public Dictionary<string, object> ToTrent()
//     {
//         Dictionary<string, object> dict = new Dictionary<string, object>();
//         dict["velocity"] = LocalVelocity;
//         return dict;
//     }

//     public void FromTrent(Dictionary<string, object> dict)
//     {
//         LocalVelocity = (Vector3)dict["velocity"];
//     }
// }
