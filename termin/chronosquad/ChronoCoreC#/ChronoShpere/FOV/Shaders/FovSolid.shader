Shader "Unlit/FovSolidDepth"
{
    Properties
    {
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        ZWrite On
        ZTest LEqual
        Cull Off
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
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float4 viewPos : TEXCOORD0;
            };

            sampler2D _MainTex;
            float4 _MainTex_ST;
            uniform float4x4 _Proj;
            uniform float4x4 _View;

            v2f vert (appdata v)
            {
                v2f o;
                //o.vertex = UnityObjectToClipPos(v.vertex);

                float4x4 V = UNITY_MATRIX_V;
                float4x4 P = UNITY_MATRIX_P;
                

                float4 vpos = mul(V, mul(UNITY_MATRIX_M, v.vertex));
                o.vertex = mul(P, vpos);
                o.viewPos = vpos / vpos.w;
                return o;
            }

            float4 frag (v2f i) : SV_Target
            {
                float z = -i.viewPos.z;
                if (z < 0) {
                    discard;
                }

                if (z > 100) {
                    float4(1, 0, 0, 1);
                }

                float depth = z / 100;
                float4 col = float4(depth, 0, 0, 1);
                return col;
            }
            ENDCG
        }
    }
}
