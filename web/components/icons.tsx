import { AiOutlineClose, AiOutlineEllipsis, AiOutlinePlus, AiOutlineWarning } from "react-icons/ai"
import { BiHistory } from "react-icons/bi"
import {
  BsActivity,
  BsCameraVideo,
  BsCheck2,
  BsChevronDown,
  BsChevronLeft,
  BsChevronRight,
  BsChevronUp,
  BsDoorClosed,
  BsDoorOpen,
  BsFolder2,
  BsMoonStars,
  BsRobot,
  BsShieldCheck,
  BsShieldX,
  BsSun,
} from "react-icons/bs"
import { FaRegFileImage, FaSort, FaUserAlt, FaUsers } from "react-icons/fa"
import { ImSpinner8 } from "react-icons/im"
import { LuCpu, LuRefreshCw, LuSend, LuSettings } from "react-icons/lu"
import { MdDeleteForever, MdOutlineLogout, MdOutlineRouter } from "react-icons/md"
import { RxDashboard, RxMixerHorizontal } from "react-icons/rx"
import { TbListCheck, TbReportSearch } from "react-icons/tb"

const icons = {
  // Navigation
  dashboard: RxDashboard,
  decisions: TbListCheck,
  chat: BsRobot,
  devices: MdOutlineRouter,
  users: FaUsers,
  audit: TbReportSearch,
  settings: LuSettings,

  // Devices
  gateway: LuCpu,
  camera: BsCameraVideo,
  doorOpen: BsDoorOpen,
  doorClosed: BsDoorClosed,
  folder: BsFolder2,
  image: FaRegFileImage,
  refresh: LuRefreshCw,

  // Decisions
  permit: BsShieldCheck,
  deny: BsShieldX,
  activity: BsActivity,

  // Mode toggle
  moon: BsMoonStars,
  sun: BsSun,

  // Common
  back: BsChevronLeft,
  next: BsChevronRight,
  up: BsChevronUp,
  down: BsChevronDown,
  close: AiOutlineClose,
  trash: MdDeleteForever,
  spinner: ImSpinner8,
  userAlt: FaUserAlt,
  ellipsis: AiOutlineEllipsis,
  warning: AiOutlineWarning,
  add: AiOutlinePlus,
  history: BiHistory,
  signout: MdOutlineLogout,
  sort: FaSort,
  mixer: RxMixerHorizontal,
  check: BsCheck2,
  send: LuSend,
}

export type IconKeys = keyof typeof icons
export const Icons: Record<IconKeys, React.ElementType> = icons
