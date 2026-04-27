export default function ErrorBlock({ message, onRetry }) {
  return (
    <div className="error-block">
      <p className="error-block-message">{message}</p>
      {onRetry ? (
        <button type="button" className="ghost-button" onClick={onRetry}>
          Tentar novamente
        </button>
      ) : null}
    </div>
  );
}
