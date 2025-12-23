/**
 * UT Status Badge Web Component
 *
 * Usage:
 *   <ut-status-badge status="completed"></ut-status-badge>
 *   <ut-status-badge status="running" text="Processing..."></ut-status-badge>
 *   <ut-status-badge status="failed" text="Error"></ut-status-badge>
 *
 * Status options: pending, running, completed, failed, partial
 */

class UTStatusBadge extends HTMLElement {
  static observedAttributes = ['status', 'text'];

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.render();
  }

  attributeChangedCallback() {
    this.render();
  }

  get status() {
    return this.getAttribute('status') || 'pending';
  }

  get text() {
    return this.getAttribute('text') || this.getDefaultText();
  }

  getDefaultText() {
    const textMap = {
      'pending': 'Pending',
      'running': 'Running',
      'completed': 'Completed',
      'failed': 'Failed',
      'partial': 'Partial',
      'staging': 'Staging',
      'processing': 'Processing',
    };
    return textMap[this.status] || 'Unknown';
  }

  getStyles() {
    const colors = {
      'pending': '--ut-grey-02',
      'running': '--ut-blue',
      'completed': '--ut-darkgreen',
      'failed': '--ut-darkred',
      'partial': '--ut-red',
      'staging': '--ut-purple',
      'processing': '--ut-blue',
    };

    const bgColors = {
      'pending': '--ut-grey-05',
      'running': '--ut-blue-light',
      'completed': '--ut-darkgreen-light',
      'failed': '--ut-darkred-light',
      'partial': '--ut-red-light',
      'staging': '--ut-purple-light',
      'processing': '--ut-blue-light',
    };

    return `
      <style>
        @import url('/static/css/ut-brand.css');

        :host {
          display: inline-flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.25rem 0.75rem;
          border-radius: 4px;
          font-family: 'Arial Narrow', Arial, sans-serif;
          font-weight: 600;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          background-color: var(${bgColors[this.status] || '--ut-grey-05'});
          color: var(${colors[this.status] || '--ut-grey-02'});
          transition: all 0.2s ease;
        }

        .dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background-color: currentColor;
        }

        .dot.running {
          animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.2); }
        }
      </style>
    `;
  }

  render() {
    const isRunning = this.status === 'running' || this.status === 'processing';
    const dotClass = isRunning ? 'dot running' : 'dot';

    this.shadowRoot.innerHTML = `
      ${this.getStyles()}
      <span class="${dotClass}"></span>
      <span class="text">${this.text}</span>
    `;
  }
}

customElements.define('ut-status-badge', UTStatusBadge);

export default UTStatusBadge;
