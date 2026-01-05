Shader "Unlit/GeometryMapsShader"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
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
                float2 uv2 : TEXCOORD1;
            };

            struct v2f
            {
                float2 uv : TEXCOORD0;
                float2 uv2 : TEXCOORD1;
                float4 vertex : SV_POSITION;
            };

            uniform int SightCollectionSize;           

            uniform float4x4  Sight0_ViewMatrix;
            uniform float4x4  Sight0_ProjMatrix;
            uniform float     Sight0_Distance;
            uniform float3    Sight0_CameraPosition;
            uniform sampler2D Sight0;
            
            uniform float4x4  Sight1_ViewMatrix;
            uniform float4x4  Sight1_ProjMatrix;
            uniform float     Sight1_Distance;
            uniform float3    Sight1_CameraPosition;
            uniform sampler2D Sight1;
            
            uniform float4x4  Sight2_ViewMatrix;
            uniform float4x4  Sight2_ProjMatrix;
            uniform float     Sight2_Distance;
            uniform float3    Sight2_CameraPosition;
            uniform sampler2D Sight2;

            uniform float4x4  Sight3_ViewMatrix;
            uniform float4x4  Sight3_ProjMatrix;
            uniform float     Sight3_Distance;
            uniform float3    Sight3_CameraPosition;
            uniform sampler2D Sight3;
            
            uniform float4x4  Sight4_ViewMatrix;
            uniform float4x4  Sight4_ProjMatrix;
            uniform float     Sight4_Distance;
            uniform float3    Sight4_CameraPosition;
            uniform sampler2D Sight4;

            uniform float4x4  Sight5_ViewMatrix;
            uniform float4x4  Sight5_ProjMatrix;
            uniform float     Sight5_Distance;
            uniform float3    Sight5_CameraPosition;
            uniform sampler2D Sight5;

            uniform float4x4  Sight6_ViewMatrix;
            uniform float4x4  Sight6_ProjMatrix;
            uniform float     Sight6_Distance;
            uniform float3    Sight6_CameraPosition;
            uniform sampler2D Sight6;

            uniform float4x4  Sight7_ViewMatrix;
            uniform float4x4  Sight7_ProjMatrix;
            uniform float     Sight7_Distance;
            uniform float3    Sight7_CameraPosition;
            uniform sampler2D Sight7;

            uniform float4x4  Sight8_ViewMatrix;
            uniform float4x4  Sight8_ProjMatrix;
            uniform float     Sight8_Distance;
            uniform float3    Sight8_CameraPosition;
            uniform sampler2D Sight8;

            uniform float4x4  Sight9_ViewMatrix;
            uniform float4x4  Sight9_ProjMatrix;
            uniform float     Sight9_Distance;
            uniform float3    Sight9_CameraPosition;
            uniform sampler2D Sight9;

            uniform float4x4 ModelMatrix;
            uniform float3 ModelScale;
            uniform float3 MaxScale;
            uniform float3 MinScale;

            sampler2D _MainTex;
            float4 _MainTex_ST;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                return o;
            }
  
            float2 get_uv(float4 vertex) 
            {
                float2 uv = vertex.xy / vertex.w;
                uv.x = (uv.x + 1) / 2;
                uv.y = (uv.y + 1) / 2;
                return uv;
            }
            
            bool in_line_of_sight(float clossest, float distance) 
            {
                return distance < clossest + 0.00; //|| distance <= 0.02;
            }

            float SampleBilinear(sampler2D smp, float4 v) {
                float2 uv = get_uv(v);
                float z = v.z;

                if (z < 0) 
                    discard;

                if (uv.x < 0 || uv.x > 1 || uv.y < 0 || uv.y > 1) {
                    discard;
                }
                return tex2D(smp, uv);
            }

            int camera_test(
                sampler2D sight, 
                float4x4 view_matrix,
                float4x4 proj_matrix,  
                float4 coords) 
            {
                float4 view = mul(view_matrix, coords);
                float4 proj = mul(proj_matrix, view);
                proj = proj / proj.w;
                
                if (-view.z < 0) 
                    return 0;
                if (proj.x < -1 || proj.x > 1) 
                    return 0;
                if (proj.y < -1 || proj.y > 1) 
                    return 0;
                
                float depth_by_tex = SampleBilinear(sight, proj) * 100;
                float depth_by_geom = -view.z;
                float depth_diff = abs(depth_by_tex - depth_by_geom);
                if (depth_diff > 0.1) 
                    return 0;

                return 1;
            }

            

            float3 CameraPosition(int i) 
            {
                if (i == 0) return Sight0_CameraPosition;
                if (i == 1) return Sight1_CameraPosition;
                if (i == 2) return Sight2_CameraPosition;
                if (i == 3) return Sight3_CameraPosition;
                if (i == 4) return Sight4_CameraPosition;
                if (i == 5) return Sight5_CameraPosition;
                if (i == 6) return Sight6_CameraPosition;
                if (i == 7) return Sight7_CameraPosition;
                if (i == 8) return Sight8_CameraPosition;
                 return Sight9_CameraPosition; 
            }

            float4x4 CameraViewMatrix(int i) 
            {
                if (i == 0) return Sight0_ViewMatrix;
                if (i == 1) return Sight1_ViewMatrix;
                if (i == 2) return Sight2_ViewMatrix;
                if (i == 3) return Sight3_ViewMatrix;
                if (i == 4) return Sight4_ViewMatrix;
                if (i == 5) return Sight5_ViewMatrix;
                if (i == 6) return Sight6_ViewMatrix;
                if (i == 7) return Sight7_ViewMatrix;
                if (i == 8) return Sight8_ViewMatrix;
                 return Sight9_ViewMatrix; 
            }

            float4x4 CameraProjMatrix(int i) 
            {
                if (i == 0) return Sight0_ProjMatrix;
                if (i == 1) return Sight1_ProjMatrix;
                if (i == 2) return Sight2_ProjMatrix;
                if (i == 3) return Sight3_ProjMatrix;
                if (i == 4) return Sight4_ProjMatrix;
                if (i == 5) return Sight5_ProjMatrix;
                if (i == 6) return Sight6_ProjMatrix;
                if (i == 7) return Sight7_ProjMatrix;
                if (i == 8) return Sight8_ProjMatrix;
                 return Sight9_ProjMatrix; 
            }

            fixed4 frag (v2f i) : SV_Target
            {
                float near_distance = 1.8;
                fixed4 coords = tex2D(_MainTex, i.uv);
                //return coords;
                fixed3 coords_xyz = MinScale + coords.xyz * (MaxScale - MinScale);
                coords = fixed4(coords_xyz, 1);
                coords = mul(ModelMatrix, coords);

                float distance0 = distance(Sight0_CameraPosition, coords.xyz);
                int test0 = camera_test(Sight0, Sight0_ViewMatrix, Sight0_ProjMatrix, coords);
                if (test0 == 1) 
                    return fixed4(0, 1, 0, 1);
                if (SightCollectionSize < 2) 
                    return fixed4(0, 0, 0, 0);

                float distance1 = distance(Sight1_CameraPosition, coords.xyz);
                int test1 = camera_test(Sight1, Sight1_ViewMatrix, Sight1_ProjMatrix, coords);
                if (test1 == 1) 
                    return fixed4(0, 1, 0, 1);
                if (SightCollectionSize < 3)
                    return fixed4(0, 0, 0, 0);

                float distance2 = distance(Sight2_CameraPosition, coords.xyz);
                int test2 = camera_test(Sight2, Sight2_ViewMatrix, Sight2_ProjMatrix, coords);
                if (test2 == 1) 
                    return fixed4(0, 1, 0, 1);
                if (SightCollectionSize < 4)
                    return fixed4(0, 0, 0, 0);

                float distance3 = distance(Sight3_CameraPosition, coords.xyz);
                int test3 = camera_test(Sight3, Sight3_ViewMatrix, Sight3_ProjMatrix, coords);
                if (test3 == 1) 
                    return fixed4(0, 1, 0, 1);
                if (SightCollectionSize < 5)
                    return fixed4(0, 0, 0, 0);

                float distance4 = distance(Sight4_CameraPosition, coords.xyz);
                int test4 = camera_test(Sight4, Sight4_ViewMatrix, Sight4_ProjMatrix, coords);
                if (test4 == 1) 
                    return fixed4(0, 1, 0, 1);
                if (SightCollectionSize < 6)
                    return fixed4(0, 0, 0, 0);

                // int test = test0 + test1 + test2 + test3 + test4;
                // //test = 1;

                // if (test == 0)
                //     return fixed4(0, 0, 0, 0);
                // else
                //     return fixed4(0, 1, 0, 1);

                return fixed4(0, 0, 0, 0);
            }

            ENDCG
        }
    }
}
