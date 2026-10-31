import MotionHeading from "./MotionHeading";
export default function PageTitle({
  eyebrow,
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
        <span className="eyebrow">{eyebrow}</span>
        <MotionHeading text={heading} />
        <p>{copy}</p>
      </div>
      {action}
    </div>
  );
}
