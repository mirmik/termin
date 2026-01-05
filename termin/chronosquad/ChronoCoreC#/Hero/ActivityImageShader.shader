Shader "Unlit/ActivityImageShader"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
    }
    SubShader
    {
        Tags { "RenderType"="Transparent" "Queue"="Transparent" }
        Blend SrcAlpha OneMinusSrcAlpha
        LOD 100

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag

            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float2 uv : TEXCOORD0;
                float4 vertex : SV_POSITION;
            };

            sampler2D _MainTex;
            float4 _MainTex_ST;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                return o;
            }

            float cross2 (float2 a, float2 b)
            {
                return a.x * b.y - a.y * b.x;
            }

            float2 normalize2 (float2 a)
            {
                float len = length(a);
                return a / len;
            }

            uniform float discard_angle = 30.0f;

            fixed4 frag (v2f i) : SV_Target
            {
                discard_angle = discard_angle * 3.6f;

                float angle = atan2(-(i.uv.x - 0.5f), -(i.uv.y - 0.5f));
                angle = angle + 3.1415926535897932384626433832795f;
                float angle_deg = angle * 180.0f / 3.1415926535897932384626433832795f;

        
                fixed4 col = tex2D(_MainTex, i.uv);
                if (angle_deg > discard_angle)
                    col.a = 0.5f;
            
                return col;
            }
            ENDCG
        }
    }
}
