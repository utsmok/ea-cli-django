/**
 * UT Progress Bar Web Component
 *
 * Usage:
 *   <ut-progress-bar value="45" max="100"></ut-progress-bar>
 *   <ut-progress-bar value="75" max="100" label="Loading..."></ut-progress-bar>
 *   <ut-progress-bar value="30" max="100" status="warning"></ut-progress-bar>
 *
 * Attributes:
 *   value: Current progress value (0-100)
 *   max: Maximum value (default: 100)
 *   label: Optional label text
 *   status: Optional status variant (default, success, warning, error)
 *   animated: Add shimmer animation (default: true)
 */

class UTProgressBar extends HTMLElement {
  static observedAttributes = ['value', 'max', 'label', 'status', 'animated'];

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

  get value() {
    return parseInt(this.getAttribute('value')) || 0;
  }

  get max() {
    return parseInt(this.getAttribute('max')) || 100;
  }

  get label() {
    return this.getAttribute('label') || '';
  }

  get status() {
    return this.getAttribute('status') || 'default';
  }

  get animated() {
    return this.getAttribute('animated') !== 'false';
  }

  get percentage() {
    return Math.min(Math.max((this.value / this.max) * 100, 0), 100);
  }

  getColor() {
    const colors = {
      'default': 'var(--ut-blue)',
      'success': 'var(--ut-darkgreen)',
      'warning': 'var(--ut-red)',
      'error': 'var(--ut-darkred)',
    };
    return colors[this.status] || colors['default'];
  }

  getStyles() {
    return `
      <style>
        @import url('/static/css/ut-brand.css');

        :host {
          display: block;
          width: 100%;
        }

        .container {
          width: 100%;
        }

        .label-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.5rem;
          font-family: 'Arial', sans-serif;
          font-size: 0.875rem;
          color: var(--ut-grey-02);
        }

        .label-text {
          font-weight: 500;
        }

        .percentage-text {
          font-weight: 600;
          color: var(--ut-off-black);
        }

        .progress-track {
          height: 8px;
          border-radius: 4px;
          background-color: var(--ut-grey-04);
          overflow: hidden;
          position: relative;
        }

        .progress-fill {
          height: 100%;
          width: ${this.percentage}%;
          background: linear-gradient(90deg, ${this.getColor()}, calc(${this.getColor()} - 20%));
          border-radius: 4px;
          transition: width 0.3s ease;
          position: relative;
        }

        .progress-fill.animated::after {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: linear-gradient(
            90deg,
            transparent,
            rgba(255, 255, 255, 0.3),
            transparent
          );
          animation: shimmer 2s infinite;
        }

        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      </style>
    `;
  }

  render() {
    const showLabel = this.label || this.getAttribute('show-percentage') !== 'false';

    this.shadowRoot.innerHTML = `
      ${this.getStyles()}
      <div class="container">
        ${showLabel ? `
          <div class="label-row">
            <span class="label-text">${this.label}</span>
            <span class="percentage-text">${Math.round(this.percentage)}%</span>
          </div>
        ` : ''}
        <div class="progress-track">
          <div class="progress-fill ${this.animated ? 'animated' : ''}" style="width: ${this.percentage}%"></div>
        </div>
      </div>
    `;
  }
}

customElements.define('ut-progress-bar', UTProgressBar);

export default UTProgressBar;
