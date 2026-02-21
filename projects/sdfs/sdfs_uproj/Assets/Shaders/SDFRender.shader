Shader "SDF/Render"
{
    Properties
    {
        _MaxDistance ("Max Distance", Float) = 100.0
        _MaxSteps ("Max Steps", Int) = 64
        _SurfaceThreshold ("Surface Threshold", Float) = 0.001
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 100

        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float2 uv : TEXCOORD0;
                float4 vertex : SV_POSITION;
                float3 worldPos : TEXCOORD1;
            };

            float4x4 _CameraMatrix;
            float3 _CameraPosition;
            float _MaxDistance;
            int _MaxSteps;
            float _SurfaceThreshold;
            
            float3 _PrimitivePos;
            float3 _PrimitiveScale;

            float sdSphere(float3 p, float3 center, float radius)
            {
                return length(p - center) - radius;
            }

            float SceneSDF(float3 p)
            {
                return sdSphere(p, _PrimitivePos, _PrimitiveScale.x);
            }

            float3 GetNormal(float3 p)
            {
                float2 e = float2(0.001, 0.0);
                return normalize(float3(
                    SceneSDF(p + e.xyy) - SceneSDF(p - e.xyy),
                    SceneSDF(p + e.yxy) - SceneSDF(p - e.yxy),
                    SceneSDF(p + e.yyx) - SceneSDF(p - e.yyx)
                ));
            }

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = TransformObjectToHClip(v.vertex.xyz);
                o.worldPos = TransformObjectToWorld(v.vertex.xyz);
                o.uv = v.uv;
                return o;
            }

            float4 frag (v2f i) : SV_Target
            {
                float3 rayOrigin = _CameraPosition;
                float3 rayDir = normalize(i.worldPos - rayOrigin);

                float t = 0.0;
                float3 col = float3(0.1, 0.1, 0.15);

                for (int j = 0; j < _MaxSteps; j++)
                {
                    float3 p = rayOrigin + rayDir * t;
                    float d = SceneSDF(p);

                    if (d < _SurfaceThreshold)
                    {
                        float3 n = GetNormal(p);
                        float3 lightDir = normalize(float3(1.0, 1.0, 0.5));
                        float diff = max(dot(n, lightDir), 0.0);
                        float3 ambient = float3(0.2, 0.2, 0.25);
                        col = ambient + diff * float3(0.8, 0.7, 0.6);
                        break;
                    }

                    if (t > _MaxDistance)
                        break;

                    t += d;
                }

                return float4(col, 1.0);
            }
            ENDHLSL
        }
    }
}
