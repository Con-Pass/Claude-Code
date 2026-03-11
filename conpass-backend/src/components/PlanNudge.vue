<template>
  <div v-if="visible" class="plan-nudge-banner alert alert-warning d-flex align-items-center mb-3">
    <div class="plan-nudge-icon me-3 fs-4">&#x26A1;</div>
    <div class="plan-nudge-content flex-grow-1">
      <strong>{{ featureName }}</strong> はSTプランでご利用いただけます
      <br>
      <small class="text-muted">契約は、力だ。STプランで、その力を解放しましょう。</small>
    </div>
    <div class="ms-auto d-flex align-items-center gap-2">
      <router-link to="/plan/compare" class="btn btn-warning btn-sm">
        プランを見る
      </router-link>
      <button v-if="!persistent" @click="dismiss" class="btn btn-outline-secondary btn-sm">&times;</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PlanNudge',
  props: {
    featureName: {
      type: String,
      required: true
    },
    persistent: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      dismissed: false
    }
  },
  computed: {
    visible() {
      return !this.dismissed
    }
  },
  methods: {
    dismiss() {
      this.dismissed = true
      this.$emit('dismissed')
    }
  }
}
</script>

<style scoped>
.plan-nudge-banner {
  border-left: 4px solid #ffc107;
  background: linear-gradient(135deg, #fff8e1 0%, #ffffff 100%);
}
.plan-nudge-icon {
  line-height: 1;
}
</style>
