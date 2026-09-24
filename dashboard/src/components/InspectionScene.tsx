import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import { Group, MathUtils } from "three";

type InspectionSceneProps = {
  state: string;
  defectDetected: boolean;
};

type RobotArmProps = InspectionSceneProps;

function RobotArm({ state, defectDetected }: RobotArmProps) {
  const shoulder = useRef<Group>(null);
  const elbow = useRef<Group>(null);
  const scanner = useRef<Group>(null);

  const isMoving = [
    "MOVING_TO_TARGET",
    "INSPECTING",
    "ANALYZING",
    "REWORKING",
    "VERIFYING_REWORK",
  ].includes(state);

  useFrame(({ clock }) => {
    if (!shoulder.current || !elbow.current || !scanner.current) {
      return;
    }

    const time = clock.getElapsedTime();
    const scanMotion = isMoving ? Math.sin(time * 1.6) * 0.12 : 0;

    const shoulderTarget =
      state === "SYSTEM_READY" || state === "INSPECTION_COMPLETE"
        ? -0.35
        : -0.85 + scanMotion;

    const elbowTarget =
      state === "REWORKING"
        ? 1.25 + Math.sin(time * 4) * 0.1
        : 0.85 - scanMotion;

    shoulder.current.rotation.z = MathUtils.lerp(
      shoulder.current.rotation.z,
      shoulderTarget,
      0.04,
    );

    elbow.current.rotation.z = MathUtils.lerp(
      elbow.current.rotation.z,
      elbowTarget,
      0.04,
    );

    scanner.current.rotation.y += 0.015;
  });

  const scannerColor = defectDetected ? "#b6415a" : "#164f4a";

  return (
    <group position={[-1.3, -1.2, 0]}>
      <mesh castShadow position={[0, 0.15, 0]}>
        <cylinderGeometry args={[0.75, 0.9, 0.3, 48]} />
        <meshStandardMaterial color="#3d1724" />
      </mesh>

      <mesh castShadow position={[0, 0.55, 0]}>
        <cylinderGeometry args={[0.42, 0.55, 0.65, 40]} />
        <meshStandardMaterial color="#6f263d" />
      </mesh>

      <group ref={shoulder} position={[0, 0.75, 0]}>
        <mesh castShadow position={[0, 1, 0]}>
          <boxGeometry args={[0.48, 2, 0.52]} />
          <meshStandardMaterial color="#e7b8c5" />
        </mesh>

        <mesh castShadow position={[0, 0, 0]}>
          <sphereGeometry args={[0.42, 32, 32]} />
          <meshStandardMaterial color="#6f263d" />
        </mesh>

        <group ref={elbow} position={[0, 2, 0]}>
          <mesh castShadow position={[0, 0.85, 0]}>
            <boxGeometry args={[0.4, 1.7, 0.44]} />
            <meshStandardMaterial color="#f4efe7" />
          </mesh>

          <mesh castShadow position={[0, 0, 0]}>
            <sphereGeometry args={[0.36, 32, 32]} />
            <meshStandardMaterial color="#164f4a" />
          </mesh>

          <group ref={scanner} position={[0, 1.85, 0]}>
            <mesh castShadow>
              <boxGeometry args={[0.72, 0.32, 0.62]} />
              <meshStandardMaterial color={scannerColor} />
            </mesh>

            <mesh position={[0.38, 0, 0]}>
              <sphereGeometry args={[0.12, 24, 24]} />
              <meshStandardMaterial
                color={defectDetected ? "#ff6b86" : "#8ed8cf"}
                emissive={scannerColor}
                emissiveIntensity={1.2}
              />
            </mesh>
          </group>
        </group>
      </group>
    </group>
  );
}

function TargetAsset({ defectDetected }: { defectDetected: boolean }) {
  return (
    <group position={[2.2, 0.5, 0]}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[0.35, 3.4, 3]} />
        <meshStandardMaterial color="#a7b78d" />
      </mesh>

      {[-0.8, 0, 0.8].map((height, index) => (
        <mesh
          key={height}
          position={[-0.2, height, index === 1 ? 0.55 : -0.55]}
        >
          <sphereGeometry args={[0.11, 24, 24]} />
          <meshStandardMaterial
            color={
              defectDetected && index === 1
                ? "#b6415a"
                : "#fffaf3"
            }
            emissive={
              defectDetected && index === 1
                ? "#b6415a"
                : "#164f4a"
            }
            emissiveIntensity={0.8}
          />
        </mesh>
      ))}
    </group>
  );
}

export function InspectionScene({
  state,
  defectDetected,
}: InspectionSceneProps) {
  return (
    <div className="inspection-scene">
      <Canvas
        shadows
        camera={{
          position: [7, 4.5, 8],
          fov: 42,
        }}
      >
        <color attach="background" args={["#f8f3eb"]} />
        <ambientLight intensity={1.6} />
        <directionalLight
          castShadow
          intensity={2.2}
          position={[5, 8, 5]}
        />
        <pointLight
          color="#e7b8c5"
          intensity={18}
          position={[-4, 3, 3]}
        />

        <RobotArm
          state={state}
          defectDetected={defectDetected}
        />

        <TargetAsset defectDetected={defectDetected} />

        <mesh receiveShadow rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.35, 0]}>
          <planeGeometry args={[14, 14]} />
          <shadowMaterial transparent opacity={0.15} />
        </mesh>

        <gridHelper
          args={[12, 20, "#c7afa9", "#dfd4ca"]}
          position={[0, -1.34, 0]}
        />

        <OrbitControls
          enablePan={false}
          minDistance={6}
          maxDistance={13}
          minPolarAngle={0.65}
          maxPolarAngle={1.45}
        />
      </Canvas>

      <div className="scene-instructions">
        DRAG TO ROTATE · SCROLL TO ZOOM
      </div>
    </div>
  );
}