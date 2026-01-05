Shader "Unlit/TimeLineShader"
{
    Properties
    {
    }
    SubShader
    {
        Tags { "Queue" = "Geometry+1" "RenderType" = "Opaque" }
        Cull Off

        
        LOD 100

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            // make fog work
            #pragma multi_compile_fog

            #include "UnityCG.cginc"

            uniform int Dash;
            uniform float4 Center;
            uniform float DashLength;
            uniform int IsCurrent;

            uniform float4 ltrb = float4(0, 0, 1800, 1800);

            struct appdata
            {
                float4 vertex : POSITION;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
            };

            v2f vert (appdata v)
            {
                v2f o;
                // float l = ltrb.x;
                // float t = ltrb.y;
                // float r = ltrb.z;
                // float b = ltrb.w;

                // float x = (v.vertex.x - l) / (r - l) * 2.0f - 1.0f;
                // float y = (v.vertex.y - b) / (t - b) * 2.0f - 1.0f;

                o.vertex = UnityObjectToClipPos(v.vertex);
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                // if (Dash) 
                // {
                //     float2 center = Center.xy;
                //     float2 pos = i.vertex.xy;
                //     float2 dir = pos - center;
                //     float dist = length(dir);
                //     float2 norm = dir / dist;
                //     float2 dash = fmod(pos, DashLength);
                //     float2 dashCenter = fmod(center, DashLength);
                //     float2 dashDir = dash - dashCenter;
                //     float dashDist = length(dashDir);
                //     float2 dashNorm = dashDir / dashDist;
                //     // float dot = dot(norm, dashNorm);
                //     // if (dot < 0.0f) 
                //     // {
                //     //     discard;
                //     // }                    
                // }

                if (IsCurrent) 
                {
                    fixed4 col = fixed4(0, 1, 1, 1.0f);
                    return col;
                }

                fixed4 col = fixed4(0, 0.5, 0.5, 0.5f);
                return col;

            }
            ENDCG
        }
    }
}
