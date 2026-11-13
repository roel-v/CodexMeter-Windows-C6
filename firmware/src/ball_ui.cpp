#include "config.h"
#ifdef CODEXMETER_BOARD_BALL
#include <lvgl.h>
#include "ui.h"
#include "theme_registry.h"
#include "dashboard_view_model.h"
#include "compact_tokens.h"
#include <string.h>

namespace {
constexpr uint32_t BG=0x090f11, WHITE=0xf4f5fa, DIM=0xa6b1c4, BLUE=0x00b4ff;
bool waiting=true, active=true, alert_visible=false;
int page=0, flash_step=-1;
uint32_t flash_ms=0, reveal_ms=0, hold_ms=0, refresh_ms=0;
bool reveal_pending=false;
UsageModel usage;
ActivityModel activity;
lv_obj_t *pages[3], *waiting_panel, *alert_panel, *alert_title, *alert_body;
lv_obj_t *percent, *reset, *counts[3], *status[3], *tokens[2][4], *costs[2][4], *footers[2];

void visible(lv_obj_t* o,bool value) {
  if(value) lv_obj_remove_flag(o,LV_OBJ_FLAG_HIDDEN);
  else lv_obj_add_flag(o,LV_OBJ_FLAG_HIDDEN);
}
lv_obj_t* panel() {
  auto* o=lv_obj_create(lv_screen_active());
  lv_obj_remove_style_all(o);
  lv_obj_set_size(o,240,240);
  lv_obj_set_style_bg_color(o,lv_color_hex(BG),0);
  lv_obj_set_style_bg_opa(o,LV_OPA_COVER,0);
  lv_obj_remove_flag(o,LV_OBJ_FLAG_SCROLLABLE);
  return o;
}
lv_obj_t* label(lv_obj_t* parent,const char* text,int x,int y,int width,
                const lv_font_t* font,uint32_t color=WHITE,lv_text_align_t align=LV_TEXT_ALIGN_CENTER) {
  auto* o=lv_label_create(parent);
  lv_obj_set_pos(o,x,y); lv_obj_set_width(o,width);
  lv_obj_set_style_text_font(o,font,0);
  lv_obj_set_style_text_color(o,lv_color_hex(color),0);
  lv_obj_set_style_text_align(o,align,0);
  lv_label_set_long_mode(o,LV_LABEL_LONG_DOT);
  lv_label_set_text(o,text); return o;
}
void show_page() {
  for(int i=0;i<3;++i) visible(pages[i],!waiting && page==i);
  visible(waiting_panel,waiting);
  // Alert is the last-created sibling and remains above either underlying view.
}
void cost_text(char* out,size_t size,uint64_t cents,bool valid,bool partial) {
  if(!valid) { snprintf(out,size,"--"); return; }
  if(cents<100000ULL) snprintf(out,size,"$%llu.%02u%s",
      (unsigned long long)(cents/100),(unsigned)(cents%100),partial?"+":"");
  else {
    char number[24]; format_compact_tokens(number,sizeof(number),true,cents/100);
    snprintf(out,size,"$%s%s",number,partial?"+":"");
  }
}
bool sum3(const uint64_t* values,uint64_t& sum) {
  sum=0;
  for(int i=0;i<3;++i) { if(UINT64_MAX-sum<values[i]) return false; sum+=values[i]; }
  return true;
}
void refresh() {
  const auto m=build_dashboard_view_model(usage,activity,-1,false,millis());
  lv_label_set_text(percent,m.usage_valid?m.d7_percent_text:"--%");
  lv_label_set_text(reset,m.usage_valid?m.d7_reset_text:"Reset in --");
  const int values[]={m.running_count,m.waiting_count,m.done_count};
  for(int i=0;i<3;++i) {
    char text[12];
    bool valid=i==0 ? activity.valid && millis()-activity.received_ms<15000UL : m.chat_counts_valid;
    if(!valid) snprintf(text,sizeof(text),"--");
    else if(values[i]>999) snprintf(text,sizeof(text),"999+");
    else snprintf(text,sizeof(text),"%d",values[i]);
    lv_label_set_text(counts[i],text);
  }
  uint32_t color=m.data_state==DashboardDataState::Ready?0x44d88a:
      m.data_state==DashboardDataState::Waiting?DIM:0xffb84d;
  for(auto* dot:status) lv_obj_set_style_text_color(dot,lv_color_hex(color),0);
  for(int w=0;w<2;++w) {
    const auto& b=m.breakdown[w];
    uint64_t sum=0; bool sum_ok=sum3(b.cents,sum);
    for(int row=0;row<4;++row) {
      char text[32];
      bool valid=row==0?(w?m.has_last_7d_tokens:m.has_today_tokens):b.valid;
      uint64_t n=row==0?(w?m.last_7d_tokens:m.today_tokens):b.tokens[row-1];
      format_compact_tokens(text,sizeof(text),valid,n,w==1);
      lv_label_set_text(tokens[w][row],text);
      cost_text(text,sizeof(text),row==0?sum:b.cents[row-1],
                b.valid && (row!=0 || sum_ok),b.partial || b.unknown);
      lv_label_set_text(costs[w][row],text);
    }
    const char* note=!b.valid?"Breakdown unavailable":
        b.unknown?"Partial data / API cost":
        b.partial?"Some usage unpriced (+)":"API cost estimate";
    if(m.data_state==DashboardDataState::Stale) note="Stale data";
    else if(m.data_state==DashboardDataState::Error) note="Telemetry unavailable";
    lv_label_set_text(footers[w],note);
  }
}
}
void ui_init(const UiSystemHooks&) {
  lv_obj_set_style_bg_color(lv_screen_active(),lv_color_hex(BG),0);
  for(int p=0;p<3;++p) {
    pages[p]=panel();
    label(pages[p],"CodexMeter",57,19,126,&lv_font_montserrat_16);
    status[p]=label(pages[p],LV_SYMBOL_BULLET,178,22,12,&lv_font_montserrat_12,DIM);
    for(int d=0;d<3;++d) label(pages[p],LV_SYMBOL_BULLET,101+d*14,216,10,
        &lv_font_montserrat_12,d==p?BLUE:0x394351);
  }
  label(pages[0],"Weekly remaining",35,45,170,&lv_font_montserrat_14,DIM);
  percent=label(pages[0],"--%",30,66,180,&lv_font_montserrat_48,BLUE);
  reset=label(pages[0],"Reset in --",25,125,190,&lv_font_montserrat_16);
  auto* line=lv_obj_create(pages[0]);lv_obj_remove_style_all(line);
  lv_obj_set_pos(line,43,153);lv_obj_set_size(line,154,1);
  lv_obj_set_style_bg_color(line,lv_color_hex(0x394351),0);lv_obj_set_style_bg_opa(line,LV_OPA_COVER,0);
  const char* names[]={"Running","Waiting","Done"};
  for(int i=0;i<3;++i) {
    counts[i]=label(pages[0],"--",36+i*55,163,58,&lv_font_montserrat_20);
    label(pages[0],names[i],35+i*55,191,60,&lv_font_montserrat_12,DIM);
  }
  for(int w=0;w<2;++w) {
    auto* root=pages[w+1];
    label(root,w?"7 days":"Today",40,42,160,&lv_font_montserrat_24);
    label(root,"Tokens",91,73,54,&lv_font_montserrat_12,DIM,LV_TEXT_ALIGN_RIGHT);
    label(root,"USD",168,73,44,&lv_font_montserrat_12,DIM,LV_TEXT_ALIGN_RIGHT);
    const char* rows[]={"Total","Input","Cached","Output"};
    for(int r=0;r<4;++r) {
      int y=96+r*25;
      label(root,rows[r],28,y,57,&lv_font_montserrat_12,r?DIM:WHITE,LV_TEXT_ALIGN_LEFT);
      tokens[w][r]=label(root,"--",85,y,60,&lv_font_montserrat_14,WHITE,LV_TEXT_ALIGN_RIGHT);
      costs[w][r]=label(root,"--",148,y,64,&lv_font_montserrat_14,WHITE,LV_TEXT_ALIGN_RIGHT);
    }
    footers[w]=label(root,"API cost estimate",28,201,184,&lv_font_montserrat_12,DIM);
  }
  waiting_panel=panel();
  label(waiting_panel,"CodexMeter",25,77,190,&lv_font_montserrat_24);
  auto* wait=label(waiting_panel,"Waiting for\ncompanion app",28,125,184,&lv_font_montserrat_16,DIM);
  lv_label_set_long_mode(wait,LV_LABEL_LONG_WRAP);
  alert_panel=panel();
  alert_title=label(alert_panel,"Task complete!",30,65,180,&lv_font_montserrat_20);
  lv_obj_set_height(alert_title,48);
  alert_body=label(alert_panel,"",28,119,184,&lv_font_montserrat_16);
  lv_obj_set_height(alert_body,76);
  visible(alert_panel,false);show_page();refresh();
}
void ui_update_usage(const UsageModel& value) { usage=value;refresh(); }
void ui_update_activity(const ActivityModel& value) { activity=value;refresh(); }
void ui_show_alert(const AlertModel& value) {
  if(!active || !value.valid) return;
  lv_label_set_text(alert_title,value.title);lv_label_set_text(alert_body,value.body);
  alert_visible=true;flash_step=0;flash_ms=millis();reveal_pending=false;
  visible(alert_title,false);visible(alert_body,false);visible(alert_panel,true);
  lv_obj_set_style_bg_color(alert_panel,lv_color_hex(0xff0000),0);
}
void ui_set_battery(int,bool) {}
void ui_show_brightness(int) {}
void ui_tick() {
  uint32_t now=millis();
  if(now-refresh_ms>=1000) {refresh_ms=now;refresh();}
  if(!alert_visible) return;
  if(flash_step>=0 && now-flash_ms>=CODEXMETER_FLASH_STEP_MS) {
    flash_ms=now;++flash_step;
    if(flash_step>=CODEXMETER_FLASH_STEPS) {
      flash_step=-1;reveal_pending=true;reveal_ms=now;
      lv_obj_set_style_bg_color(alert_panel,lv_color_hex(BG),0);
    } else {
      const uint32_t colors[]={0xff0000,0xffff00,0x00ff00};
      lv_obj_set_style_bg_color(alert_panel,lv_color_hex(colors[flash_step%3]),0);
    }
  }
  if(reveal_pending && now-reveal_ms>=CODEXMETER_ALERT_REVEAL_DELAY_MS) {
    reveal_pending=false;hold_ms=now;visible(alert_title,true);visible(alert_body,true);
  }
  if(flash_step<0 && !reveal_pending && now-hold_ms>=CODEXMETER_ALERT_HOLD_MS) ui_dismiss_alert();
}
void ui_touch_gesture(int dx,int dy,int,int,bool tap) {
  if(!active || waiting || alert_visible || tap || abs(dx)<40 || abs(dx)*2<abs(dy)*3) return;
  page=(page+(dx<0?1:2))%3;show_page();
}
void ui_set_waiting(bool value) { waiting=value;show_page(); }
bool ui_is_waiting() { return waiting; }
void ui_set_display_active(bool value) { active=value;if(!active) ui_dismiss_alert(); }
void ui_middle_short_press() {}
void ui_settings_move(int) {}
bool ui_settings_visible() { return false; }
void ui_close_settings() {}
void ui_dismiss_alert() {alert_visible=false;flash_step=-1;reveal_pending=false;visible(alert_panel,false);}
bool ui_alert_visible() { return alert_visible; }
bool ui_set_theme(const char* id,bool) { return id && strcmp(id,"classic_tasks")==0; }
bool ui_next_theme(int,bool) { return false; }
const char* ui_theme_id() { return "classic_tasks"; }
const char* ui_theme_name() { return "Classic Tasks (Ball)"; }
void ui_set_auto_theme(bool) {}
bool ui_auto_theme_enabled() { return false; }
void ui_set_auto_theme_interval(uint16_t) {}
uint16_t ui_auto_theme_interval() { return 0; }
void ui_set_volume(int) {}
int ui_volume() { return 0; }
size_t theme_registry_count() { return 0; }
const ThemePack* theme_registry_at(size_t) { return nullptr; }
const ThemePack* theme_registry_find(const char*) { return nullptr; }
const ThemePack* theme_registry_default() { return nullptr; }
const ThemePack* theme_registry_next(const char*,int) { return nullptr; }
bool theme_registry_validate() { return true; }
#endif
