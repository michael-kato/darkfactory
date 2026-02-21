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
            
            struct SDFPrimitiveData
            {
                float3 position;
                float3 scale;
                int type;
                float blendRadius;
                int blendMode;
            };

            StructuredBuffer<SDFPrimitiveData> _Primitives;
            int _PrimitiveCount;

            float sdSphere(float3 p, float3 center, float3 scale)
            {
                return length((p - center) / scale) * min(min(scale.x, scale.y), scale.z) - 1.0;
            }

            float sdBox(float3 p, float3 center, float3 scale)
            {
                float3 q = abs(p - center) - scale;
                return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
            }

            float sdCylinder(float3 p, float3 center, float3 scale)
            {
                float2 d = abs(float2(length(p.xz - center.xz), p.y - center.y)) - float2(scale.x, scale.z);
                return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
            }

            float sdCone(float3 p, float3 center, float3 scale)
            {
                float2 q = float2(length(p.xz - center.xz), p.y - center.y);
                float2 tip = q - float2(0.0, scale.y);
                float2 mantleDir = normalize(float2(scale.y, scale.x));
                float mantle = dot(tip, mantleDir);
                float d = max(mantle, -q.y);
                float projected = dot(tip, float2(mantleDir.y, -mantleDir.x));
                if ((q.y > scale.y) && (projected < 0.0))
                {
                    d = max(d, length(tip));
                }
                if ((q.x > scale.x) && (projected > length(float2(scale.y, scale.x))))
                {
                    d = max(d, length(q - float2(scale.x, 0.0)));
                }
                return d;
            }

            float sdTorus(float3 p, float3 center, float3 scale)
            {
                float2 q = float2(length(p.xz - center.xz) - scale.x, p.y - center.y);
                return length(q) - scale.y;
            }

            float sdCapsule(float3 p, float3 center, float3 scale)
            {
                float3 pa = p - center - float3(0.0, scale.y, 0.0);
                float3 ba = float3(0.0, -2.0 * scale.y, 0.0);
                float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
                return length(pa - ba * h) - scale.x;
            }

            float GetPrimitiveDistance(float3 p, SDFPrimitiveData prim)
            {
                switch (prim.type)
                {
                    case 0: return sdSphere(p, prim.position, prim.scale);
                    case 1: return sdBox(p, prim.position, prim.scale);
                    case 2: return sdCylinder(p, prim.position, prim.scale);
                    case 3: return sdCone(p, prim.position, prim.scale);
                    case 4: return sdTorus(p, prim.position, prim.scale);
                    case 5: return sdCapsule(p, prim.position, prim.scale);
                    default: return sdSphere(p, prim.position, prim.scale);
                }
            }

            float smin(float a, float b, float k)
            {
                float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
                return lerp(b, a, h) - k * h * (1.0 - h);
            }

            float smax(float a, float b, float k)
            {
                return -smin(-a, -b, k);
            }

            float opUnion(float d1, float d2, float k)
            {
                return smin(d1, d2, k);
            }

            float opSubtraction(float d1, float d2, float k)
            {
                return smax(-d1, d2, k);
            }

            float opIntersection(float d1, float d2, float k)
            {
                return smax(d1, d2, k);
            }

            float SceneSDF(float3 p)
            {
                if (_PrimitiveCount == 0)
                    return _MaxDistance;

                float d = GetPrimitiveDistance(p, _Primitives[0]);
                
                for (int i = 1; i < _PrimitiveCount; i++)
                {
                    float primD = GetPrimitiveDistance(p, _Primitives[i]);
                    float k = _Primitives[i].blendRadius;
                    
                    switch (_Primitives[i].blendMode)
                    {
                        case 0:
                            d = opUnion(d, primD, k);
                            break;
                        case 1:
                            d = opSubtraction(d, primD, k);
                            break;
                        case 2:
                            d = opIntersection(d, primD, k);
                            break;
                    }
                }
                
                return d;
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
