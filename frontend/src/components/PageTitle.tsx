import MotionHeading from "./MotionHeading";
export default function PageTitle({
  heading,
  copy,
  action,
}: {
  eyebrow: string;
  heading: string;
  copy: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <MotionHeading text={heading} />
        <p>{copy}</p>
      </div>
      {action}
    </div>
  );
}
