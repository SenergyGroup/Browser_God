const VERTEX_SHADER = `
  attribute vec2 a_position;
  varying vec2 v_uv;
  void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
    v_uv = a_position;
  }
`;

const FRAGMENT_SHADER = `
  precision highp float;
  
  uniform sampler2D u_image;
  uniform vec2 u_resolution;
  uniform float u_time;
  
  varying vec2 v_uv;

  // --- SETTINGS ---
  #define MAX_STEPS 80
  #define STEP_SIZE 0.05
  #define GRAVITY 0.12
  
  // Dimensions
  #define BH_RADIUS 0.5
  #define DISK_INNER 0.8
  #define DISK_OUTER 4.5
  #define DISK_THICKNESS 0.17

  // --- NOISE ---
  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
  }
  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
  }
  float fbm(vec2 p) {
    float v = 0.0; float a = 0.5;
    for (int i = 0; i < 3; i++) { v += a * noise(p); p *= 2.0; a *= 0.5; }
    return v;
  }
  float starField(vec2 uv) {
    float n = hash(uv * 150.0);
    if(n > 0.99) return pow((n - 0.99) * 100.0, 3.0);
    return 0.0;
  }

  void main() {
    // 1. Setup Coordinates
    vec2 uv = v_uv;
    uv.x *= u_resolution.x / u_resolution.y;

    // 2. Camera (Tilted to see the arch)
    vec3 camPos = vec3(0.0, 1.5, -7.0); 
    vec3 camTarget = vec3(0.0, -0.5, 0.0);
    
    vec3 forward = normalize(camTarget - camPos);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), forward));
    vec3 up = cross(forward, right);
    vec3 rd = normalize(forward * 2.5 + right * uv.x + up * uv.y);

    // 3. Ray March
    vec3 pos = camPos;
    vec3 dir = rd;
    vec4 accum = vec4(0.0); // Color accumulator
    bool hitHorizon = false;

    for(int i = 0; i < MAX_STEPS; i++) {
        float distToCenter = length(pos);

        // -- Event Horizon --
        if(distToCenter < BH_RADIUS) {
            hitHorizon = true;
            break;
        }

        // -- Gravity (Bend the ray) --
        // Pull direction towards center
        vec3 toCenter = normalize(-pos);
        float force = GRAVITY / (distToCenter * distToCenter);
        dir += toCenter * force * STEP_SIZE;
        dir = normalize(dir);

        // -- Volumetric Accretion Disk --
        // Calculate distance to the disk plane (Y=0)
        float distToPlane = abs(pos.y);
        
        if(distToPlane < DISK_THICKNESS && distToCenter > DISK_INNER && distToCenter < DISK_OUTER) {
            // We are inside the disk gas!
            
            // 1. Density falls off with height and distance
            float density = 1.0 - (distToPlane / DISK_THICKNESS);
            density *= smoothstep(DISK_OUTER, DISK_OUTER - 1.0, distToCenter);
            density *= smoothstep(DISK_INNER, DISK_INNER + 0.4, distToCenter);

            // 2. Rotation & Texture
            float angle = atan(pos.z, pos.x);
            float speed = 5.0 / sqrt(distToCenter);
            float rot = u_time * speed * 0.5;
            float cloud = fbm(vec2(distToCenter * 2.0, angle * 3.0 + rot));
            
            // 3. Color Gradient (NASA Style)
            // Outer: Red/Orange. Inner: Yellow/White
            vec3 col = mix(vec3(0.8, 0.05, 0.0), vec3(1.0, 0.6, 0.1), cloud);
            
            // Hot inner rim boost
            col += vec3(0.8, 0.8, 1.0) * smoothstep(DISK_INNER + 0.5, DISK_INNER, distToCenter);

            // 4. Doppler Beaming (Left side brighter)
            // Assuming Counter-Clockwise rotation
            float side = dot(dir, vec3(1.0, 0.0, 0.0)); // Simplistic directional check
            float beaming = 1.0 - (pos.x / distToCenter) * 0.6;
            col *= beaming;

            // Accumulate
            // Volumetric rendering: color * density
            float alpha = density * 0.25; // Brightness factor
            accum.rgb += col * alpha * (1.0 - accum.a);
            accum.a += alpha;
        }
        
        // Photon Ring (Bright halo near event horizon)
        if(distToCenter < BH_RADIUS * 1.5 && distToCenter > BH_RADIUS) {
            float ring = smoothstep(BH_RADIUS * 1.5, BH_RADIUS, distToCenter);
            accum.rgb += vec3(1.0, 0.8, 0.6) * ring * 0.05 * (1.0 - accum.a);
            accum.a += ring * 0.05;
        }

        // Move ray
        pos += dir * STEP_SIZE * 3.0;

        if(accum.a > 0.98) break;
    }

    // 4. Background
    vec2 bgUV = vec2(atan(dir.z, dir.x) / 6.2831 + 0.5, asin(dir.y) / 3.14159 + 0.5);
    vec3 bg = texture2D(u_image, bgUV).rgb;

    // Procedural stars if image black
    if(length(bg) < 0.1) {
        bg += vec3(starField(bgUV));
        bg += vec3(starField(bgUV * 2.0)) * 0.5;
    }
    bg *= 0.4; // Dim background to let disk shine

    vec3 finalColor = hitHorizon ? vec3(0.0) : bg;
    finalColor = mix(finalColor, accum.rgb, accum.a);

    gl_FragColor = vec4(finalColor, 1.0);
  }
`;

export class BlackHoleRenderer {
  constructor(canvasId, imageUrl) {
    this.canvas = document.getElementById(canvasId);
    this.gl = this.canvas.getContext("webgl");
    this.imageUrl = imageUrl;
    this.program = null;
    this.texture = null;
    this.running = false;
  }

  async init() {
    if (!this.gl) return;
    this.resize();
    window.addEventListener("resize", () => this.resize());

    const vert = this.createShader(this.gl.VERTEX_SHADER, VERTEX_SHADER);
    const frag = this.createShader(this.gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    if(!vert || !frag) return;

    this.program = this.createProgram(vert, frag);
    this.gl.useProgram(this.program);

    const buf = this.gl.createBuffer();
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, buf);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), this.gl.STATIC_DRAW);
    
    const loc = this.gl.getAttribLocation(this.program, "a_position");
    this.gl.enableVertexAttribArray(loc);
    this.gl.vertexAttribPointer(loc, 2, this.gl.FLOAT, false, 0, 0);

    // Create fallback texture
    this.createPlaceholderTexture();
    
    try {
      await this.loadTexture(this.imageUrl);
    } catch (e) {
      // Ignore error, shader has procedural stars
    }

    this.running = true;
    this.render(0);
  }

  resize() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
    this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
  }

  createShader(type, src) {
    const s = this.gl.createShader(type);
    this.gl.shaderSource(s, src);
    this.gl.compileShader(s);
    if (!this.gl.getShaderParameter(s, this.gl.COMPILE_STATUS)) {
      console.error(this.gl.getShaderInfoLog(s));
      return null;
    }
    return s;
  }

  createProgram(v, f) {
    const p = this.gl.createProgram();
    this.gl.attachShader(p, v);
    this.gl.attachShader(p, f);
    this.gl.linkProgram(p);
    return p;
  }

  createPlaceholderTexture() {
    this.texture = this.gl.createTexture();
    this.gl.bindTexture(this.gl.TEXTURE_2D, this.texture);
    // 1x1 Black pixel
    this.gl.texImage2D(this.gl.TEXTURE_2D, 0, this.gl.RGBA, 1, 1, 0, this.gl.RGBA, this.gl.UNSIGNED_BYTE, new Uint8Array([0,0,0,255]));
  }

  loadTexture(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.src = url;
      img.onload = () => {
        this.gl.bindTexture(this.gl.TEXTURE_2D, this.texture);
        this.gl.texImage2D(this.gl.TEXTURE_2D, 0, this.gl.RGBA, this.gl.RGBA, this.gl.UNSIGNED_BYTE, img);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_S, this.gl.REPEAT);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_T, this.gl.CLAMP_TO_EDGE);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MIN_FILTER, this.gl.LINEAR);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MAG_FILTER, this.gl.LINEAR);
        resolve();
      };
      img.onerror = reject;
    });
  }

  render(time) {
    if (!this.running) return;
    this.gl.activeTexture(this.gl.TEXTURE0);
    this.gl.bindTexture(this.gl.TEXTURE_2D, this.texture);
    this.gl.uniform1i(this.gl.getUniformLocation(this.program, "u_image"), 0);
    this.gl.uniform2f(this.gl.getUniformLocation(this.program, "u_resolution"), this.canvas.width, this.canvas.height);
    this.gl.uniform1f(this.gl.getUniformLocation(this.program, "u_time"), time * 0.001);
    this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
    requestAnimationFrame((t) => this.render(t));
  }
}